from typing import List
from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from orm import Permission, User, Topic
from orm.base import Base

class ShoutAuthor(Base):
	__tablename__ = "shout_author"
	
	id = None
	shout = Column(ForeignKey('shout.id'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)

class ShoutTopic(Base):
	__tablename__ = 'shout_topic'
	
	id = None
	shout = Column(ForeignKey('shout.id'), primary_key = True)
	topic = Column(ForeignKey('topic.id'), primary_key = True)

class ShoutRating(Base):
	__tablename__ = "shout_rating"

	id = None
	rater_id = Column(ForeignKey('user.id'), primary_key = True)
	shout_id = Column(ForeignKey('shout.id'), primary_key = True)
	ts: str = Column(DateTime, nullable=False, default = datetime.now, comment="Timestamp")
	value = Column(Integer)

class ShoutViewByDay(Base):
	__tablename__ = "shout_view_by_day"

	id = None
	shout_id = Column(ForeignKey('shout.id'), primary_key = True)
	day: str = Column(DateTime, primary_key = True, default = datetime.now)
	value = Column(Integer)

class Shout(Base):
	__tablename__ = 'shout'

	# NOTE: automatic ID here

	slug: str = Column(String, nullable=False, unique=True)
	community: int = Column(Integer, ForeignKey("community.id"), nullable=True, comment="Community")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	replyTo: int = Column(ForeignKey("shout.id"), nullable=True)
	versionOf: int = Column(ForeignKey("shout.id"), nullable=True)
	tags: str = Column(String, nullable=True)
	published: bool = Column(Boolean, default=False)
	publishedAt: str = Column(DateTime, nullable=True)
	cover: str = Column(String, nullable = True)
	title: str = Column(String, nullable = True)
	subtitle: str = Column(String, nullable = True)
	layout: str = Column(String, nullable = True)
	authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__) # NOTE: multiple authors
	topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
	ratings = relationship(ShoutRating, foreign_keys=ShoutRating.shout_id)
	views = relationship(ShoutViewByDay)
	old_id: str = Column(String, nullable = True)
