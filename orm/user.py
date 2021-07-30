from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey #, relationship

from orm import Permission
from orm.base import Base


class User(Base):
    __tablename__ = 'user'

    email: str = Column(String, nullable=False)
    username: str = Column(String, nullable=False, comment="Name")
    password: str = Column(String, nullable=True, comment="Password")

    role_id: list = Column(ForeignKey("role.id"), nullable=True, comment="Role")
    # roles = relationship("Role") TODO: one to many, see schema.graphql
    oauth_id: str = Column(String, nullable=True)

    @classmethod
    def get_permission(cls, user_id):
        perms: List[Permission] = cls.session.query(Permission).join(User, User.role_id == Permission.role_id).filter(
            User.id == user_id).all()
        return {f"{p.operation_id}-{p.resource_id}" for p in perms}


if __name__ == '__main__':
    print(User.get_permission(user_id=1))
