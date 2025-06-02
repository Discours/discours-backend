"""
Батчевые операции с токенами для оптимизации производительности
"""

import asyncio
from typing import Any, Dict, List, Optional

from auth.jwtcodec import JWTCodec
from services.redis import redis as redis_adapter
from utils.logger import root_logger as logger

from .base import BaseTokenManager
from .types import BATCH_SIZE


class BatchTokenOperations(BaseTokenManager):
    """
    Класс для пакетных операций с токенами
    """

    async def batch_validate_tokens(self, tokens: List[str]) -> Dict[str, bool]:
        """
        Пакетная валидация токенов для улучшения производительности

        Args:
            tokens: Список токенов для валидации

        Returns:
            Dict[str, bool]: Словарь {токен: валиден}
        """
        if not tokens:
            return {}

        results = {}

        # Разбиваем на батчи для избежания блокировки Redis
        for i in range(0, len(tokens), BATCH_SIZE):
            batch = tokens[i : i + BATCH_SIZE]
            batch_results = await self._validate_token_batch(batch)
            results.update(batch_results)

        return results

    async def _validate_token_batch(self, token_batch: List[str]) -> Dict[str, bool]:
        """Валидация батча токенов"""
        results = {}

        # Создаем задачи для декодирования токенов пакетно
        decode_tasks = [asyncio.create_task(self._safe_decode_token(token)) for token in token_batch]

        decoded_payloads = await asyncio.gather(*decode_tasks, return_exceptions=True)

        # Подготавливаем ключи для проверки
        token_keys = []
        valid_tokens = []

        for token, payload in zip(token_batch, decoded_payloads):
            if isinstance(payload, Exception) or not payload or not hasattr(payload, "user_id"):
                results[token] = False
                continue

            token_key = self._make_token_key("session", payload.user_id, token)
            token_keys.append(token_key)
            valid_tokens.append(token)

        # Проверяем существование ключей пакетно
        if token_keys:
            async with redis_adapter.pipeline() as pipe:
                for key in token_keys:
                    await pipe.exists(key)
                existence_results = await pipe.execute()

            for token, exists in zip(valid_tokens, existence_results):
                results[token] = bool(exists)

        return results

    async def _safe_decode_token(self, token: str) -> Optional[Any]:
        """Безопасное декодирование токена"""
        try:
            return JWTCodec.decode(token)
        except Exception:
            return None

    async def batch_revoke_tokens(self, tokens: List[str]) -> int:
        """
        Пакетный отзыв токенов

        Args:
            tokens: Список токенов для отзыва

        Returns:
            int: Количество отозванных токенов
        """
        if not tokens:
            return 0

        revoked_count = 0

        # Обрабатываем батчами
        for i in range(0, len(tokens), BATCH_SIZE):
            batch = tokens[i : i + BATCH_SIZE]
            batch_count = await self._revoke_token_batch(batch)
            revoked_count += batch_count

        return revoked_count

    async def _revoke_token_batch(self, token_batch: List[str]) -> int:
        """Отзыв батча токенов"""
        keys_to_delete = []
        user_updates: Dict[str, set[str]] = {}  # {user_id: {tokens_to_remove}}

        # Декодируем токены и подготавливаем операции
        for token in token_batch:
            payload = await self._safe_decode_token(token)
            if payload:
                user_id = payload.user_id
                username = payload.username

                # Ключи для удаления
                new_key = self._make_token_key("session", user_id, token)
                old_key = f"{user_id}-{username}-{token}"
                keys_to_delete.extend([new_key, old_key])

                # Обновления пользовательских списков
                if user_id not in user_updates:
                    user_updates[user_id] = set()
                user_updates[user_id].add(token)

        if not keys_to_delete:
            return 0

        # Выполняем удаление пакетно
        async with redis_adapter.pipeline() as pipe:
            # Удаляем ключи токенов
            await pipe.delete(*keys_to_delete)

            # Обновляем пользовательские списки
            for user_id, tokens_to_remove in user_updates.items():
                user_tokens_key = self._make_user_tokens_key(user_id, "session")
                for token in tokens_to_remove:
                    await pipe.srem(user_tokens_key, token)

            results = await pipe.execute()

        return len([r for r in results if r > 0])

    async def cleanup_expired_tokens(self) -> int:
        """Оптимизированная очистка истекших токенов с использованием SCAN"""
        try:
            cleaned_count = 0
            cursor = 0

            # Ищем все ключи пользовательских сессий
            while True:
                cursor, keys = await redis_adapter.execute("scan", cursor, "user_sessions:*", 100)

                for user_tokens_key in keys:
                    tokens = await redis_adapter.smembers(user_tokens_key)
                    active_tokens = []

                    # Проверяем активность токенов пакетно
                    if tokens:
                        async with redis_adapter.pipeline() as pipe:
                            for token in tokens:
                                token_str = token if isinstance(token, str) else str(token)
                                session_key = self._make_token_key("session", user_tokens_key.split(":")[1], token_str)
                                await pipe.exists(session_key)
                            results = await pipe.execute()

                        for token, exists in zip(tokens, results):
                            if exists:
                                active_tokens.append(token)
                            else:
                                cleaned_count += 1

                    # Обновляем список активных токенов
                    if active_tokens:
                        async with redis_adapter.pipeline() as pipe:
                            await pipe.delete(user_tokens_key)
                            for token in active_tokens:
                                await pipe.sadd(user_tokens_key, token)
                            await pipe.execute()
                    else:
                        await redis_adapter.delete(user_tokens_key)

                if cursor == 0:
                    break

            if cleaned_count > 0:
                logger.info(f"Очищено {cleaned_count} ссылок на истекшие токены")

            return cleaned_count

        except Exception as e:
            logger.error(f"Ошибка очистки токенов: {e}")
            return 0
