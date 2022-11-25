from services.auth.roles import RoleStorage
from services.auth.users import UserStorage
from services.search import SearchService
from services.stat.viewed import ViewedStorage
from base.orm import local_session


async def storages_init():
    with local_session() as session:
        print('[main] initialize storages')
        RoleStorage.init(session)
        UserStorage.init(session)
        await SearchService.init(session)
        session.commit()
        await ViewedStorage.init()
