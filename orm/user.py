from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean,
    DateTime,
    JSON as JSONType,
)
from sqlalchemy.orm import relationship

from base.orm import Base, local_session
from orm.rbac import Role
from services.auth.roles import RoleStorage


class UserNotifications(Base):
    __tablename__ = "user_notifications"
    # id auto
    user_id = Column(Integer, ForeignKey("user.id"))
    kind = Column(String, ForeignKey("notification.kind"))
    values = Column(JSONType, nullable=True)  # [ <var1>, .. ]


class UserRating(Base):
    __tablename__ = "user_rating"

    id = None  # type: ignore
    rater = Column(ForeignKey("user.slug"), primary_key=True)
    user = Column(ForeignKey("user.slug"), primary_key=True)
    value = Column(Integer)


class UserRole(Base):
    __tablename__ = "user_role"

    id = None  # type: ignore
    user_id = Column(ForeignKey("user.id"), primary_key=True)
    role_id = Column(ForeignKey("role.id"), primary_key=True)


class AuthorFollower(Base):
    __tablename__ = "author_follower"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.slug"), primary_key=True)
    author = Column(ForeignKey("user.slug"), primary_key=True)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    auto = Column(Boolean, nullable=False, default=False)


class User(Base):
    __tablename__ = "user"

    email = Column(String, unique=True, nullable=False, comment="Email")
    username = Column(String, nullable=False, comment="Login")
    password = Column(String, nullable=True, comment="Password")
    bio = Column(String, nullable=True, comment="Bio")
    userpic = Column(String, nullable=True, comment="Userpic")
    name = Column(String, nullable=True, comment="Display name")
    slug = Column(String, unique=True, comment="User's slug")
    muted = Column(Boolean, default=False)
    emailConfirmed = Column(Boolean, default=False)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    lastSeen = Column(
        DateTime, nullable=False, default=datetime.now, comment="Was online at"
    )
    deletedAt = Column(DateTime, nullable=True, comment="Deleted at")
    links = Column(JSONType, nullable=True, comment="Links")
    oauth = Column(String, nullable=True)
    notifications = relationship(lambda: UserNotifications)
    ratings = relationship(UserRating, foreign_keys=UserRating.user)
    roles = relationship(lambda: Role, secondary=UserRole.__tablename__)
    oid = Column(String, nullable=True)

    @staticmethod
    def init_table():
        with local_session() as session:
            default = session.query(User).filter(User.slug == "anonymous").first()
        if not default:
            defaul_dict = {
                "email": "noreply@discours.io",
                "username": "noreply@discours.io",
                "name": "Аноним",
                "slug": "anonymous",
            }
            default = User.create(**defaul_dict)
            session.add(default)
            discours_dict = {
                "email": "welcome@discours.io",
                "username": "welcome@discours.io",
                "name": "Дискурс",
                "slug": "discours",
            }
            discours = User.create(**discours_dict)
            session.add(discours)
            session.commit()
        User.default_user = default

    async def get_permission(self):
        scope = {}
        for user_role in self.roles:
            role: Role = await RoleStorage.get_role(user_role.id)  # type: ignore
            for p in role.permissions:
                if p.resource_id not in scope:
                    scope[p.resource_id] = set()
                scope[p.resource_id].add(p.operation_id)
        return scope


if __name__ == "__main__":
    print(User.get_permission(user_id=1))  # type: ignore
