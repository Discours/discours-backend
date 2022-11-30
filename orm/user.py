from datetime import datetime

from sqlalchemy import JSON as JSONType
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from base.orm import Base, local_session
from orm.rbac import Role


class UserNotifications(Base):
    __tablename__ = "user_notifications"
    # id auto
    user = Column(Integer, ForeignKey("user.id"))
    kind = Column(String, ForeignKey("notification.kind"))
    values = Column(JSONType, nullable=True)  # [ <var1>, .. ]


class UserRating(Base):
    __tablename__ = "user_rating"

    id = None  # type: ignore
    raterId = Column(ForeignKey("user.id"), primary_key=True, index=True)
    user = Column(ForeignKey("user.id"), primary_key=True, index=True)
    value = Column(Integer)

    @staticmethod
    def init_table():
        pass


class UserRole(Base):
    __tablename__ = "user_role"

    id = None  # type: ignore
    user = Column(ForeignKey("user.id"), primary_key=True, index=True)
    roleId = Column(ForeignKey("role.id"), primary_key=True, index=True)


class AuthorFollower(Base):
    __tablename__ = "author_follower"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.id"), primary_key=True, index=True)
    author = Column(ForeignKey("user.id"), primary_key=True, index=True)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    auto = Column(Boolean, nullable=False, default=False)


class User(Base):
    __tablename__ = "user"
    default_user = None

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
        for role in self.roles:
            for p in role.permissions:
                if p.resourceId not in scope:
                    scope[p.resourceId] = set()
                scope[p.resourceId].add(p.operationId)

        return scope


if __name__ == "__main__":
    print(User.get_permission(user_id=1))  # type: ignore
