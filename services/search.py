import asyncio
import json
from typing import List

from base.redis import redis
from orm.shout import Shout
from resolvers.zine.load import load_shouts_by


class SearchService:
    lock = asyncio.Lock()
    # cache = {}

    @staticmethod
    async def init(session):
        async with SearchService.lock:
            print("[search.service] did nothing")
            # SearchService.cache = {}

    @staticmethod
    async def search(text, limit, offset) -> List[Shout]:
        cached = await redis.execute("GET", text)
        if not cached:
            async with SearchService.lock:
                options = {"title": text, "body": text, "limit": limit, "offset": offset}
                payload = await load_shouts_by(None, None, options)
                await redis.execute("SET", text, json.dumps(payload))
                return payload
        else:
            return json.loads(cached)
