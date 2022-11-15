from services.stat.views import Stat
from services.stat.reacted import ReactedStorage
from services.auth.roles import RoleStorage
from services.auth.users import UserStorage
from services.zine.topics import TopicStorage
from services.search import SearchService
from base.orm import local_session


async def storages_init():
    with local_session() as session:
        print('[main] initialize storages')
        await Stat.update()
        ReactedStorage.init(session)
        RoleStorage.init(session)
        UserStorage.init(session)
        TopicStorage.init(session)
        await SearchService.init(session)
        session.commit()
