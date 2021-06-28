from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Like(Base):
    __tablename__ = 'like'

    author_id: str = Column(ForeignKey("user.id"), nullable=False, comment="Author")
    value: str = Column(String, nullable=False, comment="Value")
    shout: str = Column(ForeignKey("shout.id"), nullable=True, comment="Liked shout")
    user: str = Column(ForeignKey("user.id"), nullable=True, comment="Liked user")

    # TODO: add resolvers, debug, etc.