from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime

from orm import Permission
from orm.base import Base


class Shout(Base):
	__tablename__ = 'shout'

	slug: str = Column(String, primary_key=True)
	org_id: int = Column(Integer, ForeignKey("organization.id"), nullable=False, comment="Organization")
	author_id: int = Column(Integer, ForeignKey("user.id"), nullable = False, comment="Author")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	replyTo: str = Column(ForeignKey("shout.slug"), nullable=True)
	versionOf: str = Column(ForeignKey("shout.slug"), nullable=True)
	tags: str = Column(String, nullable=True)
	topics: str = Column(String, nullable=True)
	views: int = Column(Integer, default=0)

	# TODO: add all the fields
