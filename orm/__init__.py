from orm.rbac import Operation, Resource, Permission, Role
from orm.community import Community
from orm.user import User
from orm.message import Message
from orm.topic import Topic
from orm.notification import Notification
from orm.shout import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay,\
	ShoutRatingStorage, ShoutViewStorage
from orm.base import Base, engine, local_session
from orm.comment import Comment, CommentRating

__all__ = ["User", "Role", "Operation", "Permission", "Message", "Shout", "Topic", "Notification", "ShoutRating", "Comment", "CommentRating"]

Base.metadata.create_all(engine)
Operation.init_table()
Resource.init_table()

with local_session() as session:
	ShoutRatingStorage.init(session)
	ShoutViewStorage.init(session)
