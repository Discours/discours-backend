import asyncio

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
        async with SearchService.lock:
            by = {
                "title": text,
                "body": text
            }
            return await load_shouts_by(None, None, by, limit, offset)
