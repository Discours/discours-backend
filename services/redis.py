import logging

from redis.asyncio import Redis

from settings import REDIS_URL

# Set redis logging level to suppress DEBUG messages
logger = logging.getLogger("redis")
logger.setLevel(logging.WARNING)


class RedisService:
    def __init__(self, uri=REDIS_URL):
        self._uri: str = uri
        self.pubsub_channels = []
        self._client = None

    async def connect(self):
        if self._uri and self._client is None:
            self._client = await Redis.from_url(self._uri, decode_responses=True)
            logger.info("Redis connection was established.")

    async def disconnect(self):
        if isinstance(self._client, Redis):
            await self._client.close()
            logger.info("Redis connection was closed.")

    async def execute(self, command, *args, **kwargs):
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            logger.info(f"[redis] Автоматически установлено соединение при выполнении команды {command}")
            
        if self._client:
            try:
                logger.debug(f"{command}")  # {args[0]}") # {args} {kwargs}")
                for arg in args:
                    if isinstance(arg, dict):
                        if arg.get("_sa_instance_state"):
                            del arg["_sa_instance_state"]
                r = await self._client.execute_command(command, *args, **kwargs)
                # logger.debug(type(r))
                # logger.debug(r)
                return r
            except Exception as e:
                logger.error(e)

    def pipeline(self):
        """
        Возвращает пайплайн Redis для выполнения нескольких команд в одной транзакции.

        Returns:
            Pipeline: объект pipeline Redis
        """
        if self._client is None:
            # Выбрасываем исключение, так как pipeline нельзя создать до подключения
            raise Exception("Redis client is not initialized. Call redis.connect() first.")
            
        return self._client.pipeline()

    async def subscribe(self, *channels):
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        async with self._client.pubsub() as pubsub:
            for channel in channels:
                await pubsub.subscribe(channel)
                self.pubsub_channels.append(channel)

    async def unsubscribe(self, *channels):
        if self._client is None:
            return
            
        async with self._client.pubsub() as pubsub:
            for channel in channels:
                await pubsub.unsubscribe(channel)
                self.pubsub_channels.remove(channel)

    async def publish(self, channel, data):
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        await self._client.publish(channel, data)

    async def set(self, key, data, ex=None):
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        # Prepare the command arguments
        args = [key, data]

        # If an expiration time is provided, add it to the arguments
        if ex is not None:
            args.append("EX")
            args.append(ex)

        # Execute the command with the provided arguments
        await self.execute("set", *args)

    async def get(self, key):
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        return await self.execute("get", key)

    async def delete(self, *keys):
        """
        Удаляет ключи из Redis.

        Args:
            *keys: Ключи для удаления

        Returns:
            int: Количество удаленных ключей
        """
        if not keys:
            return 0
            
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        return await self._client.delete(*keys)

    async def hmset(self, key, mapping):
        """
        Устанавливает несколько полей хеша.

        Args:
            key: Ключ хеша
            mapping: Словарь с полями и значениями
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        await self._client.hset(key, mapping=mapping)

    async def expire(self, key, seconds):
        """
        Устанавливает время жизни ключа.

        Args:
            key: Ключ
            seconds: Время жизни в секундах
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        await self._client.expire(key, seconds)

    async def sadd(self, key, *values):
        """
        Добавляет значения в множество.

        Args:
            key: Ключ множества
            *values: Значения для добавления
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        await self._client.sadd(key, *values)

    async def srem(self, key, *values):
        """
        Удаляет значения из множества.

        Args:
            key: Ключ множества
            *values: Значения для удаления
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        await self._client.srem(key, *values)

    async def smembers(self, key):
        """
        Получает все элементы множества.

        Args:
            key: Ключ множества

        Returns:
            set: Множество элементов
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        return await self._client.smembers(key)
    
    async def exists(self, key):
        """
        Проверяет, существует ли ключ в Redis.

        Args:
            key: Ключ для проверки

        Returns:
            bool: True, если ключ существует, False в противном случае
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()    
            
        return await self._client.exists(key)
    
    async def expire(self, key, seconds):
        """
        Устанавливает время жизни ключа.

        Args:
            key: Ключ
            seconds: Время жизни в секундах
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        return await self._client.expire(key, seconds)

    async def keys(self, pattern):
        """
        Возвращает все ключи, соответствующие шаблону.

        Args:
            pattern: Шаблон для поиска ключей
        """
        # Автоматически подключаемся к Redis, если соединение не установлено
        if self._client is None:
            await self.connect()
            
        return await self._client.keys(pattern)
    
    


redis = RedisService()

__all__ = ["redis"]
