from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, JSON as JSONType
from sqlalchemy.orm import relationship
from orm.base import Base

import asyncio

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

class TopicStorage:
	topics = {}
	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = TopicStorage
		topics = session.query(Topic)
		self.topics = dict([(topic.slug, topic) for topic in topics])
		for topic in self.topics.values():
			self.load_parents(topic)

	@staticmethod
	def load_parents(topic):
		self = TopicStorage
		parents = []
		for parent in self.topics.values():
			if topic.slug in parent.children:
				parents.append(parent.slug)
		topic.parents = parents
		return topic

	@staticmethod
	async def get_topics(slugs):
		self = TopicStorage
		async with self.lock:
			if not slugs:
				return self.topics.values()
			topics = filter(lambda topic: topic.slug in slugs, self.topics.values())
			return list(topics)

	@staticmethod
	async def get_topics_by_community(community):
		self = TopicStorage
		async with self.lock:
			topics = filter(lambda topic: topic.community == community, self.topics.values())
			return list(topics)

	@staticmethod
	async def add_topic(topic):
		self = TopicStorage
		async with self.lock:
			self.topics[topic.slug] = topic
			self.load_parents(topic)
