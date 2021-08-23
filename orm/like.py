from typing import List

from sqlalchemy import Column, Integer, String, ForeignKey, Datetime

from orm import Permission
from orm.base import Base


class Like(Base):
	__tablename__ = 'like'

	id: int = None
	user_id: str = Column(ForeignKey("user.id"), comment="Author", primary_key = True)
	shout: str = Column(String, ForeignKey("shout.slug"), comment="Liked shout slug", primary_key = True)
	value: int = Column(Integer, nullable=False, comment="Value")

	# TODO: add resolvers, debug, etc.
