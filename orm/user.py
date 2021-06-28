from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey

from orm import Permission
from orm.base import Base


class User(Base):
    __tablename__ = 'user'

    name: str = Column(String, nullable=False, comment="Name")
    password: str = Column(String, nullable=False, comment="Password")
    # phone: str = Column(String, comment="Phone")
    # age: int = Column(Integer, comment="Age")
    role_id: int = Column(ForeignKey("role.id"), nullable=False, comment="Role")

    @classmethod
    def get_permission(cls, user_id):
        perms: List[Permission] = cls.session.query(Permission).join(User, User.role_id == Permission.role_id).filter(
            User.id == user_id).all()
        return {f"{p.operation_id}-{p.resource_id}" for p in perms}


if __name__ == '__main__':
    print(User.get_permission(user_id=1))
