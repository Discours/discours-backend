from typing import List
from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from orm import Permission, User, Topic
from orm.base import Base

ShoutAuthors = Table('shout_authors',
	Base.metadata,
	Column('shout', String, ForeignKey('shout.slug')),
	Column('user_id', Integer, ForeignKey('user.id'))
)

ShoutTopics = Table('shout_topics',
	Base.metadata,
	Column('shout', String, ForeignKey('shout.slug')),
	Column('topic', String, ForeignKey('topic.slug'))
)

class Shout(Base):
	__tablename__ = 'shout'

	id = None
	slug: str = Column(String, primary_key=True)
	org_id: int = Column(Integer, ForeignKey("organization.id"), nullable=False, comment="Organization")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	replyTo: str = Column(ForeignKey("shout.slug"), nullable=True)
	versionOf: str = Column(ForeignKey("shout.slug"), nullable=True)
	tags: str = Column(String, nullable=True)
	views: int = Column(Integer, default=0)
	published: bool = Column(Boolean, default=False)
	publishedAt: str = Column(DateTime, nullable=True)
	cover: str = Column(String, nullable = True)
	layout: str = Column(String, nullable = True)
	authors = relationship(lambda: User, secondary=ShoutAuthors) # NOTE: multiple authors
	topics = relationship(lambda: Topic, secondary=ShoutTopics)
