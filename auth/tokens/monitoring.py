"""
Статистика и мониторинг системы токенов
"""

import asyncio
from typing import Any, Dict

from services.redis import redis as redis_adapter
from utils.logger import root_logger as logger

from .base import BaseTokenManager
from .types import SCAN_BATCH_SIZE


class TokenMonitoring(BaseTokenManager):
    """
    Класс для мониторинга и статистики токенов
    """

    async def get_token_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по токенам для мониторинга

        Returns:
            Dict: Статистика токенов
        """
        stats = {
            "session_tokens": 0,
            "verification_tokens": 0,
            "oauth_access_tokens": 0,
            "oauth_refresh_tokens": 0,
            "user_sessions": 0,
            "memory_usage": 0,
        }

        try:
            # Считаем токены по типам используя SCAN
            patterns = {
                "session_tokens": "session:*",
                "verification_tokens": "verification_token:*",
                "oauth_access_tokens": "oauth_access:*",
                "oauth_refresh_tokens": "oauth_refresh:*",
                "user_sessions": "user_sessions:*",
            }

            count_tasks = [self._count_keys_by_pattern(pattern) for pattern in patterns.values()]
            counts = await asyncio.gather(*count_tasks)

            for (stat_name, _), count in zip(patterns.items(), counts):
                stats[stat_name] = count

            # Получаем информацию о памяти Redis
            memory_info = await redis_adapter.execute("INFO", "MEMORY")
            stats["memory_usage"] = memory_info.get("used_memory", 0)

        except Exception as e:
            logger.error(f"Ошибка получения статистики токенов: {e}")

        return stats

    async def _count_keys_by_pattern(self, pattern: str) -> int:
        """Подсчет ключей по паттерну используя SCAN"""
        count = 0
        cursor = 0

        while True:
            cursor, keys = await redis_adapter.execute("scan", cursor, pattern, SCAN_BATCH_SIZE)
            count += len(keys)

            if cursor == 0:
                break

        return count

    async def optimize_memory_usage(self) -> Dict[str, Any]:
        """
        Оптимизирует использование памяти Redis

        Returns:
            Dict: Результаты оптимизации
        """
        results = {"cleaned_expired": 0, "optimized_structures": 0, "memory_saved": 0}

        try:
            # Очищаем истекшие токены
            from .batch import BatchTokenOperations

            batch_ops = BatchTokenOperations()
            cleaned = await batch_ops.cleanup_expired_tokens()
            results["cleaned_expired"] = cleaned

            # Оптимизируем структуры данных
            optimized = await self._optimize_data_structures()
            results["optimized_structures"] = optimized

            # Запускаем сборку мусора Redis
            await redis_adapter.execute("MEMORY", "PURGE")

            logger.info(f"Оптимизация памяти завершена: {results}")

        except Exception as e:
            logger.error(f"Ошибка оптимизации памяти: {e}")

        return results

    async def _optimize_data_structures(self) -> int:
        """Оптимизирует структуры данных Redis"""
        optimized_count = 0
        cursor = 0

        # Оптимизируем пользовательские списки сессий
        while True:
            cursor, keys = await redis_adapter.execute("scan", cursor, "user_sessions:*", SCAN_BATCH_SIZE)

            for key in keys:
                try:
                    # Проверяем размер множества
                    size = await redis_adapter.execute("scard", key)
                    if size == 0:
                        await redis_adapter.delete(key)
                        optimized_count += 1
                    elif size > 100:  # Слишком много сессий у одного пользователя
                        # Оставляем только последние 50 сессий
                        members = await redis_adapter.execute("smembers", key)
                        if len(members) > 50:
                            members_list = list(members)
                            to_remove = members_list[:-50]
                            if to_remove:
                                await redis_adapter.srem(key, *to_remove)
                                optimized_count += len(to_remove)

                except Exception as e:
                    logger.error(f"Ошибка оптимизации ключа {key}: {e}")
                    continue

            if cursor == 0:
                break

        return optimized_count

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья системы токенов

        Returns:
            Dict: Результаты проверки
        """
        health: Dict[str, Any] = {
            "status": "healthy",
            "redis_connected": False,
            "token_operations": False,
            "errors": [],
        }

        try:
            # Проверяем подключение к Redis
            await redis_adapter.ping()
            health["redis_connected"] = True

            # Тестируем основные операции с токенами
            from .sessions import SessionTokenManager

            session_manager = SessionTokenManager()

            test_user_id = "health_check_user"
            test_token = await session_manager.create_session(test_user_id)

            if test_token:
                # Проверяем валидацию
                valid, _ = await session_manager.validate_session_token(test_token)
                if valid:
                    # Проверяем отзыв
                    revoked = await session_manager.revoke_session_token(test_token)
                    if revoked:
                        health["token_operations"] = True
                    else:
                        health["errors"].append("Failed to revoke test token")  # type: ignore[misc]
                else:
                    health["errors"].append("Failed to validate test token")  # type: ignore[misc]
            else:
                health["errors"].append("Failed to create test token")  # type: ignore[misc]

        except Exception as e:
            health["errors"].append(f"Health check error: {e}")  # type: ignore[misc]

        if health["errors"]:
            health["status"] = "unhealthy"

        return health
