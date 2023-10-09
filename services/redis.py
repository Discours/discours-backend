import asyncio
import aredis
from settings import REDIS_URL


class RedisCache:
    def __init__(self, uri=REDIS_URL):
        self._uri: str = uri
        self.pubsub_channels = []
        self._instance = None

    async def connect(self):
        self._instance = aredis.StrictRedis.from_url(self._uri, decode_responses=True)

    async def disconnect(self):
        if self._instance:
            self._instance.connection_pool.disconnect()
            self._instance = None

    async def execute(self, command, *args, **kwargs):
        while not self._instance:
            await asyncio.sleep(1)
        try:
            print("[redis] " + command + " " + " ".join(args))
            return await self._instance.execute_command(command, *args, **kwargs)
        except Exception:
            pass

    async def subscribe(self, *channels):
        if not self._instance:
            await self.connect()
        for channel in channels:
            await self._instance.subscribe(channel)
            self.pubsub_channels.append(channel)

    async def unsubscribe(self, *channels):
        if not self._instance:
            return
        for channel in channels:
            await self._instance.unsubscribe(channel)
            self.pubsub_channels.remove(channel)

    async def publish(self, channel, data):
        if not self._instance:
            return
        await self._instance.publish(channel, data)

    async def lrange(self, key, start, stop):
        print(f"[redis] LRANGE {key} {start} {stop}")
        return await self._instance.lrange(key, start, stop)

    async def mget(self, key, *keys):
        print(f"[redis] MGET {key} {keys}")
        return await self._instance.mget(key, *keys)


redis = RedisCache()

__all__ = ["redis"]
