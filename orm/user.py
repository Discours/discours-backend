from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, JSON as JSONType
from sqlalchemy.orm import relationship

from orm import Permission
from orm.base import Base, local_session
from orm.notification import UserNotification

class UserRating(Base):
	__tablename__ = 'user_rating'

	createdBy: int = Column(Integer, ForeignKey("user.id"), primary_key = True)
	value: int = Column(Integer, nullable=False)

class UserRole(Base):
	__tablename__ = 'user_role'
	
	id: int = Column(Integer, primary_key = True)
	user_id: int = Column(Integer, ForeignKey("user.id"))
	role_id str = Column(String, ForeignKey("role.name"))

class User(Base):
	__tablename__ = 'user'

	email: str = Column(String, unique=True, nullable=False, comment="Email")
	username: str = Column(String, nullable=False, comment="Login")
	password: str = Column(String, nullable=True, comment="Password")
	bio: str = Column(String, nullable=True, comment="Bio")
	userpic: str = Column(String, nullable=True, comment="Userpic")
	viewname: str = Column(String, nullable=True, comment="Display name")
	rating: int = Column(Integer, nullable=True, comment="Rating")
	slug: str = Column(String, unique=True, nullable=True, comment="Slug")
	muted: bool = Column(Boolean, default=False)
	emailConfirmed: bool = Column(Boolean, default=False)
	createdAt: DateTime = Column(DateTime, nullable=False, comment="Created at")
	wasOnlineAt: DateTime = Column(DateTime, nullable=False, comment="Was online at")
	links: JSONType = Column(JSONType, nullable=True, comment="Links")
	oauth: str = Column(String, nullable=True)
	notifications = relationship(lambda: UserNotification)
	ratings = relationship(lambda: UserRating)
	roles = relationship(lambda: UserRole)

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


if __name__ == '__main__':
	print(User.get_permission(user_id=1))
