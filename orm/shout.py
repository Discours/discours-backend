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
	__tablename__ = "shout_ratings"

	id = None
	rater_id = Column(ForeignKey('user.id'), primary_key = True)
	shout_id = Column(ForeignKey('shout.id'), primary_key = True)
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
	views: int = Column(Integer, default=0)
	published: bool = Column(Boolean, default=False)
	publishedAt: str = Column(DateTime, nullable=True)
	cover: str = Column(String, nullable = True)
	title: str = Column(String, nullable = True)
	subtitle: str = Column(String, nullable = True)
	layout: str = Column(String, nullable = True)
	authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__) # NOTE: multiple authors
	topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
	rating: int = Column(Integer, nullable=True, comment="Rating")
	ratings = relationship(ShoutRating, foreign_keys=ShoutRating.shout_id)
	old_id: str = Column(String, nullable = True)
