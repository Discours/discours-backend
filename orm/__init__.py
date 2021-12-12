from orm.rbac import Operation, Resource, Permission, Role, RoleStorage
from orm.community import Community
from orm.user import User, UserRating, UserRole, UserStorage
from orm.message import Message
from orm.topic import Topic, TopicSubscription, TopicStorage
from orm.notification import Notification
from orm.shout import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay,\
	ShoutRatingStorage, ShoutViewStorage
from orm.base import Base, engine, local_session
from orm.comment import Comment, CommentRating

__all__ = ["User", "Role", "Community", "Operation", "Permission", "Message", "Shout", "Topic", "TopicSubscription", "Notification", "ShoutRating", "Comment", "CommentRating", "UserRating"]

Base.metadata.create_all(engine)
Operation.init_table()
Resource.init_table()
User.init_table()
Community.init_table()
Role.init_table()

with local_session() as session:
	ShoutRatingStorage.init(session)
	ShoutViewStorage.init(session)
	RoleStorage.init(session)
	UserStorage.init(session)
	TopicStorage.init(session)
