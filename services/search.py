import asyncio
from orm.shout import Shout


class SearchService:
    lock = asyncio.Lock()
    cache = {}

    @staticmethod
    async def init(session):
        async with SearchService.lock:
            SearchService.cache = {}

    @staticmethod
    async def search(text) -> [Shout]:
        async with SearchService.lock:
            return []  # TODO: implement getting shouts list
