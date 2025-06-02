"""
Управление OAuth токенов
"""

import json
import time
from typing import Optional

from services.redis import redis as redis_adapter
from utils.logger import root_logger as logger

from .base import BaseTokenManager
from .types import DEFAULT_TTL, TokenData, TokenType


class OAuthTokenManager(BaseTokenManager):
    """
    Менеджер OAuth токенов
    """

    async def store_oauth_tokens(
        self,
        user_id: str,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        additional_data: Optional[TokenData] = None,
    ) -> bool:
        """Сохраняет OAuth токены"""
        try:
            # Сохраняем access token
            access_data = {
                "token": access_token,
                "provider": provider,
                "expires_in": expires_in,
                **(additional_data or {}),
            }

            access_ttl = expires_in if expires_in else DEFAULT_TTL["oauth_access"]
            await self._create_oauth_token(user_id, access_data, access_ttl, provider, "oauth_access")

            # Сохраняем refresh token если есть
            if refresh_token:
                refresh_data = {
                    "token": refresh_token,
                    "provider": provider,
                }
                await self._create_oauth_token(
                    user_id, refresh_data, DEFAULT_TTL["oauth_refresh"], provider, "oauth_refresh"
                )

            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения OAuth токенов: {e}")
            return False

    async def _create_oauth_token(
        self, user_id: str, token_data: TokenData, ttl: int, provider: str, token_type: TokenType
    ) -> str:
        """Оптимизированное создание OAuth токена"""
        if not provider:
            error_msg = "OAuth токены требуют указания провайдера"
            raise ValueError(error_msg)

        identifier = f"{user_id}:{provider}"
        token_key = self._make_token_key(token_type, identifier)

        # Добавляем метаданные
        token_data.update(
            {"user_id": user_id, "token_type": token_type, "provider": provider, "created_at": int(time.time())}
        )

        # Используем SETEX для атомарной операции
        serialized_data = json.dumps(token_data, ensure_ascii=False)
        await redis_adapter.execute("setex", token_key, ttl, serialized_data)

        logger.info(f"Создан {token_type} токен для пользователя {user_id}, провайдер {provider}")
        return token_key

    async def get_token(self, user_id: int, provider: str, token_type: TokenType) -> Optional[TokenData]:
        """Получает токен"""
        if token_type.startswith("oauth_"):
            return await self._get_oauth_data_optimized(token_type, str(user_id), provider)
        return None

    async def _get_oauth_data_optimized(
        self, token_type: TokenType, user_id: str, provider: str
    ) -> Optional[TokenData]:
        """Оптимизированное получение OAuth данных"""
        if not user_id or not provider:
            error_msg = "OAuth токены требуют user_id и provider"
            raise ValueError(error_msg)

        identifier = f"{user_id}:{provider}"
        token_key = self._make_token_key(token_type, identifier)

        # Получаем данные и TTL в одном pipeline
        async with redis_adapter.pipeline() as pipe:
            await pipe.get(token_key)
            await pipe.ttl(token_key)
            results = await pipe.execute()

        if results[0]:
            token_data = json.loads(results[0])
            if results[1] > 0:
                token_data["ttl_remaining"] = results[1]
            return token_data
        return None

    async def revoke_oauth_tokens(self, user_id: str, provider: str) -> bool:
        """Удаляет все OAuth токены для провайдера"""
        try:
            result1 = await self._revoke_oauth_token_optimized("oauth_access", user_id, provider)
            result2 = await self._revoke_oauth_token_optimized("oauth_refresh", user_id, provider)
            return result1 or result2
        except Exception as e:
            logger.error(f"Ошибка удаления OAuth токенов: {e}")
            return False

    async def _revoke_oauth_token_optimized(self, token_type: TokenType, user_id: str, provider: str) -> bool:
        """Оптимизированный отзыв OAuth токена"""
        if not user_id or not provider:
            error_msg = "OAuth токены требуют user_id и provider"
            raise ValueError(error_msg)

        identifier = f"{user_id}:{provider}"
        token_key = self._make_token_key(token_type, identifier)
        result = await redis_adapter.delete(token_key)
        return result > 0

    async def revoke_user_oauth_tokens(self, user_id: str, token_type: TokenType) -> int:
        """Оптимизированный отзыв OAuth токенов пользователя используя SCAN"""
        count = 0
        cursor = 0
        delete_keys = []
        pattern = f"{token_type}:{user_id}:*"

        # Используем SCAN для безопасного поиска токенов
        while True:
            cursor, keys = await redis_adapter.execute("scan", cursor, pattern, 100)

            if keys:
                delete_keys.extend(keys)
                count += len(keys)

            if cursor == 0:
                break

        # Удаляем найденные токены пакетно
        if delete_keys:
            await redis_adapter.delete(*delete_keys)

        return count
