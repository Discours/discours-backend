from services.stat.viewed import ViewedStorage
from services.stat.reacted import ReactedStorage
from services.auth.roles import RoleStorage
from services.auth.users import UserStorage
from services.zine.topics import TopicStorage
from base.orm import local_session


async def storages_init():
    with local_session() as session:
        print('[main] initialize storages')
        ViewedStorage.init(session)
        ReactedStorage.init(session)
        RoleStorage.init(session)
        UserStorage.init(session)
        TopicStorage.init(session)
        session.commit()
