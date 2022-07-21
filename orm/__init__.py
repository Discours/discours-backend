from orm.rbac import Operation, Resource, Permission, Role
from storages.roles import RoleStorage
from orm.community import Community
from orm.user import User, UserRating
from orm.topic import Topic, TopicFollower
from orm.notification import Notification
from orm.shout import Shout
from orm.reaction import Reaction
from storages.topics import TopicStorage
from storages.users import UserStorage
from storages.viewed import ViewedStorage
from orm.base import Base, engine, local_session

__all__ = ["User", "Role", "Operation", "Permission", \
	"Community", "Shout", "Topic", "TopicFollower", \
    "Notification", "Reaction", "UserRating"]

Base.metadata.create_all(engine)
Operation.init_table()
Resource.init_table()
User.init_table()
Community.init_table()
Role.init_table()

with local_session() as session:
	ViewedStorage.init(session)
	RoleStorage.init(session)
	UserStorage.init(session)
	TopicStorage.init(session)
