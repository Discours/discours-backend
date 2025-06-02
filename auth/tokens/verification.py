"""
Управление токенами подтверждения
"""

import json
import secrets
import time
from typing import Optional

from services.redis import redis as redis_adapter
from utils.logger import root_logger as logger

from .base import BaseTokenManager
from .types import TokenData


class VerificationTokenManager(BaseTokenManager):
    """
    Менеджер токенов подтверждения
    """

    async def create_verification_token(
        self,
        user_id: str,
        verification_type: str,
        data: TokenData,
        ttl: Optional[int] = None,
    ) -> str:
        """Создает токен подтверждения"""
        token_data = {"verification_type": verification_type, **data}

        # TTL по типу подтверждения
        if ttl is None:
            verification_ttls = {
                "email_change": 3600,  # 1 час
                "phone_change": 600,  # 10 минут
                "password_reset": 1800,  # 30 минут
            }
            ttl = verification_ttls.get(verification_type, 3600)

        return await self._create_verification_token(user_id, token_data, ttl)

    async def _create_verification_token(
        self, user_id: str, token_data: TokenData, ttl: int, token: Optional[str] = None
    ) -> str:
        """Оптимизированное создание токена подтверждения"""
        verification_token = token or secrets.token_urlsafe(32)
        token_key = self._make_token_key("verification", user_id, verification_token)

        # Добавляем метаданные
        token_data.update({"user_id": user_id, "token_type": "verification", "created_at": int(time.time())})

        # Отменяем предыдущие токены того же типа
        verification_type = token_data.get("verification_type", "unknown")
        await self._cancel_verification_tokens_optimized(user_id, verification_type)

        # Используем SETEX для атомарной операции установки с TTL
        serialized_data = json.dumps(token_data, ensure_ascii=False)
        await redis_adapter.execute("setex", token_key, ttl, serialized_data)

        logger.info(f"Создан токен подтверждения {verification_type} для пользователя {user_id}")
        return verification_token

    async def get_verification_token_data(self, token: str) -> Optional[TokenData]:
        """Получает данные токена подтверждения"""
        token_key = self._make_token_key("verification", "", token)
        return await redis_adapter.get_and_deserialize(token_key)

    async def validate_verification_token(self, token_str: str) -> tuple[bool, Optional[TokenData]]:
        """Проверяет валидность токена подтверждения"""
        token_key = self._make_token_key("verification", "", token_str)
        token_data = await redis_adapter.get_and_deserialize(token_key)
        if token_data:
            return True, token_data
        return False, None

    async def confirm_verification_token(self, token_str: str) -> Optional[TokenData]:
        """Подтверждает и использует токен подтверждения (одноразовый)"""
        token_data = await self.get_verification_token_data(token_str)
        if token_data:
            # Удаляем токен после использования
            await self.revoke_verification_token(token_str)
            return token_data
        return None

    async def revoke_verification_token(self, token: str) -> bool:
        """Отзывает токен подтверждения"""
        token_key = self._make_token_key("verification", "", token)
        result = await redis_adapter.delete(token_key)
        return result > 0

    async def revoke_user_verification_tokens(self, user_id: str) -> int:
        """Оптимизированный отзыв токенов подтверждения пользователя используя SCAN вместо KEYS"""
        count = 0
        cursor = 0
        delete_keys = []

        # Используем SCAN для безопасного поиска токенов
        while True:
            cursor, keys = await redis_adapter.execute("scan", cursor, "verification_token:*", 100)

            # Проверяем каждый ключ в пакете
            if keys:
                async with redis_adapter.pipeline() as pipe:
                    for key in keys:
                        await pipe.get(key)
                    results = await pipe.execute()

                for key, data in zip(keys, results):
                    if data:
                        try:
                            token_data = json.loads(data)
                            if token_data.get("user_id") == user_id:
                                delete_keys.append(key)
                                count += 1
                        except (json.JSONDecodeError, TypeError):
                            continue

            if cursor == 0:
                break

        # Удаляем найденные токены пакетно
        if delete_keys:
            await redis_adapter.delete(*delete_keys)

        return count

    async def _cancel_verification_tokens_optimized(self, user_id: str, verification_type: str) -> None:
        """Оптимизированная отмена токенов подтверждения используя SCAN"""
        cursor = 0
        delete_keys = []

        while True:
            cursor, keys = await redis_adapter.execute("scan", cursor, "verification_token:*", 100)

            if keys:
                # Получаем данные пакетно
                async with redis_adapter.pipeline() as pipe:
                    for key in keys:
                        await pipe.get(key)
                    results = await pipe.execute()

                # Проверяем какие токены нужно удалить
                for key, data in zip(keys, results):
                    if data:
                        try:
                            token_data = json.loads(data)
                            if (
                                token_data.get("user_id") == user_id
                                and token_data.get("verification_type") == verification_type
                            ):
                                delete_keys.append(key)
                        except (json.JSONDecodeError, TypeError):
                            continue

            if cursor == 0:
                break

        # Удаляем найденные токены пакетно
        if delete_keys:
            await redis_adapter.delete(*delete_keys)
