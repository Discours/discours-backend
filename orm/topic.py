from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from orm.base import Base


Connection = Table('topic_connections',
	Base.metadata,
    Column('child', Integer, ForeignKey('topic.id')),
    Column('parent', Integer, ForeignKey('topic.id')),
    UniqueConstraint('parent', 'child', name='unique_usage')
)

class TopicSubscription(Base):
	__tablename__ = "topic_subscription"
	
	id = None
	topic = Column(ForeignKey('topic.id'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")

class Topic(Base):
	__tablename__ = 'topic'

	slug: str = Column(String, unique = True, nullable = False)
	title: str = Column(String, nullable=False, comment="Title")
	body: str = Column(String, nullable=True, comment="Body")
	pic: str = Column(String, nullable=True, comment="Picture")
	cat_id: str = Column(String, nullable=True, comment="Old Category ID")
	# list of Topics where the current node is the "other party" or "child"
	parents = relationship(lambda: Topic, secondary=Connection, primaryjoin=slug==Connection.c.parent, secondaryjoin=slug==Connection.c.child, viewonly=True)
	# list of Topics where the current node is the "parent" 
	children = relationship(lambda: Topic, secondary=Connection, primaryjoin=slug==Connection.c.child, secondaryjoin=slug==Connection.c.parent)
	community = Column(ForeignKey("community.slug"), nullable=True, comment="Community")

