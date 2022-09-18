from aioredis import from_url

from settings import REDIS_URL


class RedisCache:
    def __init__(self, uri=REDIS_URL):
        self._uri: str = uri
        self._instance = None

    async def connect(self):
        if self._instance is not None:
            return
        self._instance = await from_url(self._uri, encoding="utf-8")

    async def disconnect(self):
        if self._instance is None:
            return
        self._instance.close()
        # await self._instance.wait_closed()  # deprecated
        self._instance = None

    async def execute(self, command, *args, **kwargs):
        return await self._instance.execute_command(command, *args, **kwargs)

    async def lrange(self, key, start, stop):
        return await self._instance.lrange(key, start, stop)

    async def mget(self, key, *keys):
        return await self._instance.mget(key, *keys)


redis = RedisCache()

__all__ = ["redis"]
