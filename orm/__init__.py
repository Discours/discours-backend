from orm.rbac import Operation, Resource, Permission, Role
from orm.community import Community
from orm.user import User, UserRating, UserRole
from orm.message import Message
from orm.topic import Topic, TopicSubscription
from orm.notification import Notification
from orm.shout import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay,\
	ShoutRatingStorage, ShoutViewStorage
from orm.base import Base, engine, local_session
from orm.comment import Comment, CommentRating

__all__ = ["User", "Role", "Community", "Operation", "Permission", "Message", "Shout", "Topic", "TopicSubscription", "Notification", "ShoutRating", "Comment", "CommentRating", "UserRating"]

Base.metadata.create_all(engine)
Operation.init_table()
Resource.init_table()

with local_session() as session:
	ShoutRatingStorage.init(session)
	ShoutViewStorage.init(session)
