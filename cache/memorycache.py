"""
Модуль для кеширования данных с использованием Redis.
Предоставляет API, совместимый с dogpile.cache для поддержки обратной совместимости.
"""

import functools
import hashlib
import inspect
import json
import logging
import pickle
from typing import Callable, Optional

import orjson

from services.redis import redis
from utils.encoders import CustomJSONEncoder

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # время жизни кеша в секундах (5 минут)


class RedisCache:
    """
    Класс, предоставляющий API, совместимый с dogpile.cache, но использующий Redis.

    Примеры:
    >>> cache_region = RedisCache()
    >>> @cache_region.cache_on_arguments("my_key")
    ... def my_func(arg1, arg2):
    ...     return arg1 + arg2
    """

    def __init__(self, ttl: int = DEFAULT_TTL):
        """
        Инициализация объекта кеша.

        Args:
            ttl: Время жизни кеша в секундах
        """
        self.ttl = ttl

    def cache_on_arguments(self, cache_key: Optional[str] = None) -> Callable:
        """
        Декоратор для кеширования результатов функций с использованием Redis.

        Args:
            cache_key: Опциональный базовый ключ кеша. Если не указан, генерируется из сигнатуры функции.

        Returns:
            Декоратор для кеширования функции

        Примеры:
        >>> @cache_region.cache_on_arguments("users")
        ... def get_users():
        ...     return db.query(User).all()
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Генерация ключа кеша
                key = self._generate_cache_key(func, cache_key, *args, **kwargs)

                # Попытка получить данные из кеша
                cached_data = await redis.get(key)
                if cached_data:
                    try:
                        return orjson.loads(cached_data)
                    except Exception:
                        # Если не удалось десериализовать как JSON, попробуем как pickle
                        return pickle.loads(cached_data.encode())

                # Вызов оригинальной функции, если данных в кеше нет
                result = func(*args, **kwargs)

                # Сохранение результата в кеш
                try:
                    # Пытаемся сериализовать как JSON
                    serialized = json.dumps(result, cls=CustomJSONEncoder)
                except (TypeError, ValueError):
                    # Если не удалось, используем pickle
                    serialized = pickle.dumps(result).decode()

                await redis.set(key, serialized, ex=self.ttl)
                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Для функций, которые не являются корутинами
                # Генерация ключа кеша
                key = self._generate_cache_key(func, cache_key, *args, **kwargs)

                # Синхронная версия не использует await, поэтому результат всегда вычисляется
                result = func(*args, **kwargs)

                # Асинхронно записываем в кэш (будет выполнено позже)
                try:
                    import asyncio

                    serialized = json.dumps(result, cls=CustomJSONEncoder)
                    asyncio.create_task(redis.set(key, serialized, ex=self.ttl))
                except Exception as e:
                    logger.error(f"Ошибка при кешировании результата: {e}")

                return result

            # Возвращаем асинхронный или синхронный враппер в зависимости от типа функции
            if inspect.iscoroutinefunction(func):
                return wrapper
            else:
                return sync_wrapper

        return decorator

    def _generate_cache_key(self, func: Callable, base_key: Optional[str], *args, **kwargs) -> str:
        """
        Генерирует ключ кеша на основе функции и её аргументов.

        Args:
            func: Кешируемая функция
            base_key: Базовый ключ кеша
            *args: Позиционные аргументы функции
            **kwargs: Именованные аргументы функции

        Returns:
            Строковый ключ для кеша
        """
        if base_key:
            key_prefix = f"cache:{base_key}"
        else:
            key_prefix = f"cache:{func.__module__}.{func.__name__}"

        # Создаем хеш аргументов
        arg_hash = hashlib.md5()

        # Добавляем позиционные аргументы
        for arg in args:
            try:
                arg_hash.update(str(arg).encode())
            except Exception:
                arg_hash.update(str(id(arg)).encode())

        # Добавляем именованные аргументы (сортируем для детерминированности)
        for k in sorted(kwargs.keys()):
            try:
                arg_hash.update(f"{k}:{kwargs[k]}".encode())
            except Exception:
                arg_hash.update(f"{k}:{id(kwargs[k])}".encode())

        return f"{key_prefix}:{arg_hash.hexdigest()}"

    def invalidate(self, func: Callable, *args, **kwargs) -> None:
        """
        Инвалидирует (удаляет) кеш для конкретной функции с конкретными аргументами.

        Args:
            func: Кешированная функция
            *args: Позиционные аргументы функции
            **kwargs: Именованные аргументы функции
        """
        key = self._generate_cache_key(func, None, *args, **kwargs)
        import asyncio

        asyncio.create_task(redis.execute("DEL", key))


# Экземпляр класса RedisCache для использования в коде
cache_region = RedisCache()
