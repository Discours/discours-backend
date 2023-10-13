import redis.asyncio as redis
from settings import REDIS_URL

class RedisCache:
    def __init__(self, uri=REDIS_URL):
        self._uri: str = uri
        self.pubsub_channels = []
        self._redis = None

    async def connect(self):
        self._redis = redis.Redis.from_url(self._uri, decode_responses=True)

    async def disconnect(self):
        await self._redis.aclose()

    async def execute(self, command, *args, **kwargs):
        if not self._redis:
            await self.connect()
        try:
            print("[redis] " + command + " " + " ".join(args))
            return await self._redis.execute_command(command, *args, **kwargs)
        except Exception as e:
            print(f"[redis] error: {e}")
            return None

    async def subscribe(self, *channels):
        if not self._redis:
            await self.connect()
        async with self._redis.pubsub() as pubsub:
            for channel in channels:
                await pubsub.subscribe(channel)
                self.pubsub_channels.append(channel)

    async def unsubscribe(self, *channels):
        if not self._redis:
            return
        async with self._redis.pubsub() as pubsub:
            for channel in channels:
                await pubsub.unsubscribe(channel)
                self.pubsub_channels.remove(channel)

    async def publish(self, channel, data):
        if not self._redis:
            return
        await self._redis.publish(channel, data)

    async def lrange(self, key, start, stop):
        print(f"[redis] LRANGE {key} {start} {stop}")
        return await self._redis.lrange(key, start, stop)

    async def mget(self, key, *keys):
        print(f"[redis] MGET {key} {keys}")
        return await self._redis.mget(key, *keys)

redis = RedisCache()

__all__ = ["redis"]
