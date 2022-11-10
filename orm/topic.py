from datetime import datetime

from sqlalchemy import JSON as JSONType
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String

from base.orm import Base


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

    slug = Column(String, unique=True)
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
