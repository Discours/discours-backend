from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from orm.user import User
from orm.topic import Topic, ShoutTopic
from orm.reaction import Reaction, get_bookmarked
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage
from base.orm import Base, local_session


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
    caption: str = Column(String, nullable = True, default = "")
    
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
    async def stat(self):
        reacted = []
        try:
            with local_session() as session:
                reacted = session.query(Reaction).where(Reaction.shout == self.slug).all()
        except Exception as e:
            print(e)
        return {
                "viewed": await ViewedStorage.get_shout(self.slug),
                "reacted": await ReactedStorage.get_shout(self.slug),
                "rating": await ReactedStorage.get_rating(self.slug),
                "bookmarked": get_bookmarked(reacted)
            }
