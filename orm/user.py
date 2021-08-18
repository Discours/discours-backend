from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from orm import Permission
from orm.base import Base, local_session


class UserRole(Base):
	__tablename__ = 'user_role'
	
	id = None
	user_id: int = Column(ForeignKey("user.id"), primary_key = True)
	role_id: int = Column(ForeignKey("role.id"), primary_key = True)

class User(Base):
	__tablename__ = 'user'

	email: str = Column(String, unique=True, nullable=False)
	username: str = Column(String, nullable=False, comment="Name")
	password: str = Column(String, nullable=True, comment="Password")

	oauth_id: str = Column(String, nullable=True)

	roles = relationship("Role", secondary=UserRole.__table__)

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
