from datetime import datetime

from sqlalchemy import Column, Boolean, String, ForeignKey, DateTime, JSON as JSONType

from base.orm import Base


class ShoutTopic(Base):
    __tablename__ = "shout_topic"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    topic = Column(ForeignKey("topic.slug"), primary_key=True)


class TopicFollower(Base):
    __tablename__ = "topic_followers"

    id = None  # type: ignore
    follower = Column(ForeignKey("user.slug"), primary_key=True)
    topic = Column(ForeignKey("topic.slug"), primary_key=True)
    createdAt = Column(
        DateTime, nullable=False, default=datetime.now, comment="Created at"
    )
    auto = Column(Boolean, nullable=False, default=False)


class Topic(Base):
    __tablename__ = "topic"

    id = None  # type: ignore
    slug = Column(String, primary_key=True)
    title = Column(String, nullable=False, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    children = Column(
        JSONType, nullable=True, default=[], comment="list of children topics"
    )
    community = Column(
        ForeignKey("community.slug"), nullable=False, comment="Community"
    )
    oid = Column(String, nullable=True, comment="Old ID")
