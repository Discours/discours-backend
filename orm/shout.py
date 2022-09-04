from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from orm.user import User
from orm.topic import Topic, ShoutTopic
from orm.reaction import Reaction
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage
from base.orm import Base


class ShoutReactionsFollower(Base):
    __tablename__ = "shout_reactions_followers"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.slug"), primary_key=True)
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    auto = Column(Boolean, nullable=False, default=False)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    deletedAt = Column(DateTime, nullable=True)


class ShoutAuthor(Base):
    __tablename__ = "shout_author"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    user = Column(ForeignKey("user.slug"), primary_key=True)
    caption = Column(String, nullable=True, default="")


class ShoutAllowed(Base):
    __tablename__ = "shout_allowed"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    user = Column(ForeignKey("user.id"), primary_key=True)


class Shout(Base):
    __tablename__ = "shout"

    id = None  # type: ignore
    slug = Column(String, primary_key=True)
    community = Column(
        Integer, ForeignKey("community.id"), nullable=False, comment="Community"
    )
    body = Column(String, nullable=False, comment="Body")
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    updatedAt = Column(DateTime, nullable=True, comment="Updated at")
    replyTo = Column(ForeignKey("shout.slug"), nullable=True)
    versionOf = Column(ForeignKey("shout.slug"), nullable=True)
    tags = Column(String, nullable=True)
    publishedBy = Column(ForeignKey("user.id"), nullable=True)
    publishedAt = Column(DateTime, nullable=True)
    cover = Column(String, nullable=True)
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    layout = Column(String, nullable=True)
    reactions = relationship(lambda: Reaction)
    authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__)
    topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
    mainTopic = Column(ForeignKey("topic.slug"), nullable=True)
    visibleFor = relationship(lambda: User, secondary=ShoutAllowed.__tablename__)
    draft = Column(Boolean, default=True)
    oid = Column(String, nullable=True)

    @property
    async def stat(self):
        return {
            "viewed": await ViewedStorage.get_shout(self.slug),
            "reacted": len(await ReactedStorage.get_shout(self.slug)),
            "commented": len(await ReactedStorage.get_comments(self.slug)),
            "rating": await ReactedStorage.get_rating(self.slug),
        }
