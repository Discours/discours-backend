from base.orm import Base, engine
from orm.community import Community
from orm.notification import Notification
from orm.rbac import Operation, Resource, Permission, Role
from orm.reaction import Reaction
from orm.shout import Shout
from orm.topic import Topic, TopicFollower
from orm.user import User, UserRating

# NOTE: keep orm module isolated

__all__ = [
    "User",
    "Role",
    "Operation",
    "Permission",
    "Community",
    "Shout",
    "Topic",
    "TopicFollower",
    "Notification",
    "Reaction",
    "UserRating",
]


def init_tables():
    Base.metadata.create_all(engine)
    Operation.init_table()
    Resource.init_table()
    User.init_table()
    Community.init_table()
    Role.init_table()
    UserRating.init_table()
    Shout.init_table()
    print("[orm] tables initialized")
