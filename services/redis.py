import json
import logging
from typing import TYPE_CHECKING, Any, Optional, Set, Union

import redis.asyncio as aioredis
from redis.asyncio import Redis

if TYPE_CHECKING:
    pass  # type: ignore[attr-defined]

from settings import REDIS_URL
from utils.logger import root_logger as logger

logger = logging.getLogger(__name__)

# Set redis logging level to suppress DEBUG messages
redis_logger = logging.getLogger("redis")
redis_logger.setLevel(logging.WARNING)


class RedisService:
    """
    Сервис для работы с Redis с поддержкой пулов соединений.

    Provides connection pooling and proper error handling for Redis operations.
    """

    def __init__(self, redis_url: str = REDIS_URL) -> None:
        self._client: Optional[Redis[Any]] = None
        self._redis_url = redis_url
        self._is_available = aioredis is not None

        if not self._is_available:
            logger.warning("Redis is not available - aioredis not installed")

    async def connect(self) -> None:
        """Establish Redis connection"""
        if not self._is_available:
            return

        # Закрываем существующее соединение если есть
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

        try:
            self._client = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle decoding manually
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            await self._client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            if self._client:
                try:
                    await self._client.close()
                except Exception:
                    pass
            self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._client is not None and self._is_available

    def pipeline(self) -> Any:  # Returns Pipeline but we can't import it safely
        """Create a Redis pipeline"""
        if self._client:
            return self._client.pipeline()
        return None

    async def execute(self, command: str, *args: Any) -> Any:
        """Execute a Redis command"""
        if not self._is_available:
            logger.debug(f"Redis not available, skipping command: {command}")
            return None

        # Проверяем и восстанавливаем соединение при необходимости
        if not self.is_connected:
            logger.info("Redis not connected, attempting to reconnect...")
            await self.connect()

        if not self.is_connected:
            logger.error(f"Failed to establish Redis connection for command: {command}")
            return None

        try:
            # Get the command method from the client
            cmd_method = getattr(self._client, command.lower(), None)
            if cmd_method is None:
                logger.error(f"Unknown Redis command: {command}")
                return None

            result = await cmd_method(*args)
            return result
        except (ConnectionError, AttributeError, OSError) as e:
            logger.warning(f"Redis connection lost during {command}, attempting to reconnect: {e}")
            # Попытка переподключения
            await self.connect()
            if self.is_connected:
                try:
                    cmd_method = getattr(self._client, command.lower(), None)
                    if cmd_method is not None:
                        result = await cmd_method(*args)
                        return result
                except Exception as retry_e:
                    logger.error(f"Redis retry failed for {command}: {retry_e}")
            return None
        except Exception as e:
            logger.error(f"Redis command failed {command}: {e}")
            return None

    async def get(self, key: str) -> Optional[Union[str, bytes]]:
        """Get value by key"""
        return await self.execute("get", key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set key-value pair with optional expiration"""
        if ex is not None:
            result = await self.execute("setex", key, ex, value)
        else:
            result = await self.execute("set", key, value)
        return result is not None

    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        result = await self.execute("delete", *keys)
        return result or 0

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        result = await self.execute("exists", key)
        return bool(result)

    async def publish(self, channel: str, data: Any) -> None:
        """Publish message to channel"""
        if not self.is_connected or self._client is None:
            logger.debug(f"Redis not available, skipping publish to {channel}")
            return

        try:
            await self._client.publish(channel, data)
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")

    async def hset(self, key: str, field: str, value: Any) -> None:
        """Set hash field"""
        await self.execute("hset", key, field, value)

    async def hget(self, key: str, field: str) -> Optional[Union[str, bytes]]:
        """Get hash field"""
        return await self.execute("hget", key, field)

    async def hgetall(self, key: str) -> dict[str, Any]:
        """Get all hash fields"""
        result = await self.execute("hgetall", key)
        return result or {}

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern"""
        result = await self.execute("keys", pattern)
        return result or []

    async def smembers(self, key: str) -> Set[str]:
        """Get set members"""
        if not self.is_connected or self._client is None:
            return set()
        try:
            result = await self._client.smembers(key)
            if result:
                return {str(item.decode("utf-8") if isinstance(item, bytes) else item) for item in result}
            return set()
        except Exception as e:
            logger.error(f"Redis smembers command failed for {key}: {e}")
            return set()

    async def sadd(self, key: str, *members: str) -> int:
        """Add members to set"""
        result = await self.execute("sadd", key, *members)
        return result or 0

    async def srem(self, key: str, *members: str) -> int:
        """Remove members from set"""
        result = await self.execute("srem", key, *members)
        return result or 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration"""
        result = await self.execute("expire", key, seconds)
        return bool(result)

    async def serialize_and_set(self, key: str, data: Any, ex: Optional[int] = None) -> bool:
        """Serialize data to JSON and store in Redis"""
        try:
            if isinstance(data, (str, bytes)):
                serialized_data: bytes = data.encode("utf-8") if isinstance(data, str) else data
            else:
                serialized_data = json.dumps(data).encode("utf-8")

            return await self.set(key, serialized_data, ex=ex)
        except Exception as e:
            logger.error(f"Failed to serialize and set {key}: {e}")
            return False

    async def get_and_deserialize(self, key: str) -> Any:
        """Get data from Redis and deserialize from JSON"""
        try:
            data = await self.get(key)
            if data is None:
                return None

            if isinstance(data, bytes):
                data = data.decode("utf-8")

            return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get and deserialize {key}: {e}")
            return None

    async def ping(self) -> bool:
        """Ping Redis server"""
        if not self.is_connected or self._client is None:
            return False
        try:
            result = await self._client.ping()
            return bool(result)
        except Exception:
            return False

    async def execute_pipeline(self, commands: list[tuple[str, tuple[Any, ...]]]) -> list[Any]:
        """
        Выполняет список команд через pipeline для лучшей производительности.
        Избегает использования async context manager для pipeline чтобы избежать deprecated warnings.

        Args:
            commands: Список кортежей (команда, аргументы)

        Returns:
            Список результатов выполнения команд
        """
        if not self.is_connected or self._client is None:
            logger.warning("Redis not connected, cannot execute pipeline")
            return []

        try:
            pipe = self.pipeline()
            if pipe is None:
                logger.error("Failed to create Redis pipeline")
                return []

            # Добавляем команды в pipeline
            for command, args in commands:
                cmd_method = getattr(pipe, command.lower(), None)
                if cmd_method is not None:
                    cmd_method(*args)
                else:
                    logger.error(f"Unknown Redis command in pipeline: {command}")

            # Выполняем pipeline
            results = await pipe.execute()
            return results

        except Exception as e:
            logger.error(f"Redis pipeline execution failed: {e}")
            return []


# Global Redis instance
redis = RedisService()


async def init_redis() -> None:
    """Initialize Redis connection"""
    await redis.connect()


async def close_redis() -> None:
    """Close Redis connection"""
    await redis.disconnect()
