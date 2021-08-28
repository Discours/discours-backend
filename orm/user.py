from typing import List
from datetime import datetime

from sqlalchemy import Table, Column, Integer, String, ForeignKey, Boolean, DateTime, JSON as JSONType
from sqlalchemy.orm import relationship

from orm import Permission
from orm.base import Base, local_session
from orm.rbac import Role
from orm.topic import Topic

class UserNotifications(Base):
	__tablename__ = 'user_notifications'

	id: int = Column(Integer, primary_key = True)
	user_id: int = Column(Integer, ForeignKey("user.id"))
	kind: str = Column(String, ForeignKey("notification.kind"))
	values: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]

class UserRatings(Base):
	__tablename__ = "user_ratings"

	id = None
	rater_id = Column(ForeignKey('user.id'), primary_key = True)
	user_id = Column(ForeignKey('user.id'), primary_key = True)
	value = Column(Integer)

UserRoles = Table("user_roles",
	Base.metadata,
	Column('user_id', Integer, ForeignKey('user.id'), primary_key = True),
	Column('role_id', Integer, ForeignKey('role.id'), primary_key = True)
)

UserTopics = Table("user_topics",
	Base.metadata,
	Column('user_id', Integer, ForeignKey('user.id'), primary_key = True),
	Column('topic_id', Integer, ForeignKey('topic.id'), primary_key = True)
)

class User(Base):
	__tablename__ = "user"

	email: str = Column(String, unique=True, nullable=False, comment="Email")
	username: str = Column(String, nullable=False, comment="Login")
	password: str = Column(String, nullable=True, comment="Password")
	bio: str = Column(String, nullable=True, comment="Bio")
	userpic: str = Column(String, nullable=True, comment="Userpic")
	viewname: str = Column(String, nullable=True, comment="Display name")
	rating: int = Column(Integer, nullable=True, comment="Rating")
	slug: str = Column(String, unique=True, comment="User's slug")
	muted: bool = Column(Boolean, default=False)
	emailConfirmed: bool = Column(Boolean, default=False)
	createdAt: DateTime = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	wasOnlineAt: DateTime = Column(DateTime, nullable=False, default = datetime.now, comment="Was online at")
	links: JSONType = Column(JSONType, nullable=True, comment="Links")
	oauth: str = Column(String, nullable=True)
	notifications = relationship(lambda: UserNotifications)
	ratings = relationship(UserRatings, foreign_keys=UserRatings.user_id)
	roles = relationship(lambda: Role, secondary=UserRoles)
	topics = relationship(lambda: Topic, secondary=UserTopics)

	@classmethod
	def get_permission(cls, user_id):
		scope = {}
		with local_session() as session:
			user = session.query(User).filter(User.id == user_id).first()
			for role in user.roles:
				for p in role.permissions:
					if not p.resource_id in scope:
						scope[p.resource_id] = set()
					scope[p.resource_id].add(p.operation_id)
		return scope


if __name__ == "__main__":
	print(User.get_permission(user_id=1))
