import asyncio
from orm.shout import Shout


class SearchService:
    lock = asyncio.Lock()
    cache = {}

    @staticmethod
    def init(session):
        self = SearchService
        async with self.lock:
            self.cache = {}

    @staticmethod
    async def search(text) -> [Shout]:
        self = SearchService
        async with self.lock:
            return []  # TODO: implement getting shouts list
