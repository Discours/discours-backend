from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from orm import Permission
from orm.base import Base

class Topic(Base):
	__tablename__ = 'topic'

	slug: str = Column(String, unique = True, nullable = False, primary_key=True)
	org_id: str = Column(ForeignKey("organization.id"), nullable=False)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	createdBy: str = Column(ForeignKey("user.id"), nullable=False, comment="Author")
	value: str = Column(String, nullable=False, comment="Value")
	alters = relationship(lambda: Topic, backref=backref("topic", remote_side=[slug]))
	alter_id: str = Column(ForeignKey("topic.slug"))
	# TODO: add all the fields
