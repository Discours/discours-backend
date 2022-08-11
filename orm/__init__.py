from orm.rbac import Operation, Resource, Permission, Role
from services.auth.roles import RoleStorage
from orm.community import Community
from orm.user import User, UserRating
from orm.topic import Topic, TopicFollower
from orm.notification import Notification
from orm.shout import Shout
from orm.reaction import Reaction
from services.zine.topics import TopicStorage
from services.auth.users import UserStorage
from services.stat.viewed import ViewedStorage
from base.orm import Base, engine, local_session

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
