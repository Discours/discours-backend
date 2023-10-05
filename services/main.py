from services.search import SearchService
from services.viewed import ViewedStorage
from services.db import local_session


async def storages_init():
    with local_session() as session:
        await SearchService.init(session)
        await ViewedStorage.init()
