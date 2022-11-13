from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from base.orm import Base
from orm.reaction import Reaction
from orm.topic import Topic
from orm.user import User


class ShoutTopic(Base):
    __tablename__ = "shout_topic"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    topic = Column(ForeignKey("topic.slug"), primary_key=True)


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


class Shout(Base):
    __tablename__ = "shout"

    slug = Column(String, unique=True)
    community = Column(Integer, ForeignKey("community.id"), nullable=False, comment="Community")
    lang = Column(String, nullable=False, default='ru', comment="Language")
    body = Column(String, nullable=False, comment="Body")
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    layout = Column(String, nullable=True)
    mainTopic = Column(ForeignKey("topic.slug"), nullable=True)
    cover = Column(String, nullable=True)
    authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__)
    topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
    reactions = relationship(lambda: Reaction)
    visibility = Column(String, nullable=True)  # owner authors community public
    versionOf = Column(ForeignKey("shout.slug"), nullable=True)
    lang = Column(String, default='ru')
    oid = Column(String, nullable=True)
    media = Column(JSON, nullable=True)

    createdAt = Column(DateTime, nullable=False, default=datetime.now, comment="Created at")
    updatedAt = Column(DateTime, nullable=True, comment="Updated at")
    publishedAt = Column(DateTime, nullable=True)
    deletedAt = Column(DateTime, nullable=True)

