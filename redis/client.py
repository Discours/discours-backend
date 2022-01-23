from typing import Optional

import aioredis

from settings import REDIS_URL


class Redis:
	def __init__(self, uri=REDIS_URL):
		self._uri: str = uri
		self._instance = None

	async def connect(self):
		if self._instance is not None:
			return
		self._instance = aioredis.from_url(self._uri, encoding="utf-8")

	async def disconnect(self):
		if self._instance is None:
			return
		self._instance.close()
		await self._instance.wait_closed()
		self._instance = None

	async def execute(self, command, *args, **kwargs):
		return await self._instance.execute_command(command, *args, **kwargs)

	async def lrange(self, name, start, end):
		return await self._instance.lrange(name, start, end)


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
