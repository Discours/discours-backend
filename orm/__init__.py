from orm.rbac import Community, Operation, Resource, Permission, Role
from orm.user import User
from orm.message import Message
from orm.topic import Topic
from orm.notification import Notification
from orm.shout import Shout
from orm.base import Base, engine

__all__ = ["User", "Role", "Operation", "Permission", "Message", "Shout", "Topic", "Notification"]

Base.metadata.create_all(engine)
Operation.init_table()
Resource.init_table()
