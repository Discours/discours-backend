from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, JSON as JSONType
from sqlalchemy.orm import relationship
from orm.base import Base

class TopicSubscription(Base):
	__tablename__ = "topic_subscription"
	
	id = None
	topic = Column(ForeignKey('topic.slug'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")

class Topic(Base):
	__tablename__ = 'topic'

	id = None

	slug: str = Column(String, primary_key = True)
	title: str = Column(String, nullable=False, comment="Title")
	body: str = Column(String, nullable=True, comment="Body")
	pic: str = Column(String, nullable=True, comment="Picture")
	children = Column(JSONType, nullable=True, comment="list of children topics")
	community = Column(ForeignKey("community.slug"), nullable=False, comment="Community")
