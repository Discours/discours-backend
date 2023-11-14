from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func

from base.orm import Base


class TopicFollower(Base):
    __tablename__ = "topic_followers"

    id = None
    follower: Column = Column(ForeignKey("user.id"), primary_key=True, index=True)
    topic: Column = Column(ForeignKey("topic.id"), primary_key=True, index=True)
    createdAt = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Created at"
    )
    auto = Column(Boolean, nullable=False, default=False)


class Topic(Base):
    __tablename__ = "topic"

    slug = Column(String, unique=True)
    title = Column(String, nullable=False, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    community: Column = Column(ForeignKey("community.id"), default=1, comment="Community")
    oid = Column(String, nullable=True, comment="Old ID")
