from orm.rbac import Operation, Resource, Permission, Role
from orm.community import Community
from orm.user import User
from orm.message import Message
from orm.topic import Topic
from orm.notification import Notification
from orm.shout import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay,\
	ShoutRatingStorage, ShoutViewStorage
from orm.base import Base, engine, local_session
from orm.comment import Comment

__all__ = ["User", "Role", "Operation", "Permission", "Message", "Shout", "Topic", "Notification"]

Base.metadata.create_all(engine)
Operation.init_table()
Resource.init_table()

with local_session() as session:
	rating_storage = ShoutRatingStorage(session)
	ShoutViewStorage.init(session)
