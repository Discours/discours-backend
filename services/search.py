import asyncio
import json
from base.redis import redis
from orm.shout import Shout
from resolvers.zine import load_shouts_by


class SearchService:
    lock = asyncio.Lock()
    cache = {}

    @staticmethod
    async def init(session):
        async with SearchService.lock:
            print('[search.service] init')
            SearchService.cache = {}

    @staticmethod
    async def search(text, limit, offset) -> [Shout]:
        cached = redis.execute("GET", text)
        if not cached:
            async with SearchService.lock:
                by = {
                    "title": text,
                    "body": text
                }
                payload = await load_shouts_by(None, None, by, limit, offset)
                redis.execute("SET", text, json.dumps(payload))
                return payload
        else:
            return json.loads(cached)
