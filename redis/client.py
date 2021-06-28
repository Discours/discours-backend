from typing import Optional

import aioredis
from aioredis import ConnectionsPool

from settings import REDIS_URL


class Redis:
    def __init__(self, uri=REDIS_URL):
        self._uri: str = uri
        self._pool: Optional[ConnectionsPool] = None

    async def connect(self):
        if self._pool is not None:
            return
        pool = await aioredis.create_pool(self._uri)
        self._pool = pool

    async def disconnect(self):
        if self._pool is None:
            return
        self._pool.close()
        await self._pool.wait_closed()
        self._pool = None

    async def execute(self, command, *args, **kwargs):
        return await self._pool.execute(command, *args, **kwargs, encoding="UTF-8")


async def test():
    redis = Redis()
    from datetime import datetime

    await redis.connect()
    await redis.execute("SET", "1-KEY1", 1)
    await redis.execute("SET", "1-KEY2", 1)
    await redis.execute("SET", "1-KEY3", 1)
    await redis.execute("SET", "1-KEY4", 1)
    await redis.execute("EXPIREAT", "1-KEY4", int(datetime.utcnow().timestamp()))
    v = await redis.execute("KEYS", "1-*")
    print(v)
    await redis.execute("DEL", *v)
    v = await redis.execute("KEYS", "1-*")
    print(v)


if __name__ == '__main__':
    import asyncio

    asyncio.run(test())
