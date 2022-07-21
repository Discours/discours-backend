from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from orm.user import User
from orm.topic import Topic, ShoutTopic
from orm.reaction import Reaction
from storages.reactions import ReactionsStorage
from storages.viewed import ViewedStorage
from orm.base import Base


class ShoutReactionsFollower(Base):
	__tablename__ = "shout_reactions_followers"
	
	id = None
	follower = Column(ForeignKey('user.slug'), primary_key = True)
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	auto = Column(Boolean, nullable=False, default = False)
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	deletedAt: str = Column(DateTime, nullable=True)

class ShoutAuthor(Base):
	__tablename__ = "shout_author"
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	user = Column(ForeignKey('user.slug'), primary_key = True)
	
class ShoutAllowed(Base):
	__tablename__ = "shout_allowed"
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)

class Shout(Base):
	__tablename__ = 'shout'

	id = None

	slug: str = Column(String, primary_key=True)
	community: str = Column(Integer, ForeignKey("community.id"), nullable=False, comment="Community")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	replyTo: int = Column(ForeignKey("shout.slug"), nullable=True)
	versionOf: int = Column(ForeignKey("shout.slug"), nullable=True)
	tags: str = Column(String, nullable=True)
	publishedBy: int = Column(ForeignKey("user.id"), nullable=True)
	publishedAt: str = Column(DateTime, nullable=True)
	cover: str = Column(String, nullable = True)
	title: str = Column(String, nullable = True)
	subtitle: str = Column(String, nullable = True)
	layout: str = Column(String, nullable = True)
	reactions = relationship(lambda: Reaction)
	authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__)
	topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
	mainTopic = Column(ForeignKey("topic.slug"), nullable=True)
	visibleFor = relationship(lambda: User, secondary=ShoutAllowed.__tablename__)
	draft: bool = Column(Boolean, default=True)
	oid: str = Column(String, nullable=True)

	@property
	async def stat(self) -> Dict:
		return {
			"viewed": await ViewedStorage.get_shout(self.slug),
			"reacted": await ReactionsStorage.by_shout(self.slug)
		}
