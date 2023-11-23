from base.orm import local_session
from services.search import SearchService
from services.stat.viewed import ViewedStorage


async def storages_init():
    with local_session() as session:
        print("[main] initialize SearchService")
        await SearchService.init(session)
        print("[main] SearchService initialized")
        print("[main] initialize storages")
        await ViewedStorage.init()
        print("[main] storages initialized")
