from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, JSON as JSONType
from orm.base import Base

class ShoutTopic(Base):
	__tablename__ = 'shout_topic'
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	topic = Column(ForeignKey('topic.slug'), primary_key = True)
class TopicFollower(Base):
	__tablename__ = "topic_followers"
	
	id = None
	follower = Column(ForeignKey('user.slug'), primary_key = True)
	topic = Column(ForeignKey('topic.slug'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")

class Topic(Base):
	__tablename__ = 'topic'

	id = None

	slug: str = Column(String, primary_key = True)
	title: str = Column(String, nullable=False, comment="Title")
	body: str = Column(String, nullable=True, comment="Body")
	pic: str = Column(String, nullable=True, comment="Picture")
	children = Column(JSONType, nullable=True, default = [], comment="list of children topics")
	community = Column(ForeignKey("community.slug"), nullable=False, comment="Community")
	oid: str = Column(String, nullable=True, comment="Old ID")

