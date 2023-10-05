from services.search import SearchService
from services.viewed import ViewedStorage
from services.db import local_session


async def storages_init():
    with local_session() as session:
        print("[main] initialize SearchService")
        await SearchService.init(session)
        print("[main] SearchService initialized")
        print("[main] initialize storages")
        await ViewedStorage.init()
        print("[main] storages initialized")
