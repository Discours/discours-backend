from datetime import datetime

from sqlalchemy import Boolean, Column, ForeignKey, DateTime, String
from sqlalchemy.orm import relationship
from base.orm import Base
from orm.user import User
from orm.topic import Topic


class DraftTopic(Base):
    __tablename__ = "draft_topic"

    id = None  # type: ignore
    collab = Column(ForeignKey("draft_collab.id"), primary_key=True)
    topic = Column(ForeignKey("topic.id"), primary_key=True)


class DraftAuthor(Base):
    __tablename__ = "draft_author"

    id = None  # type: ignore
    collab = Column(ForeignKey("draft_collab.id"), primary_key=True)
    author = Column(ForeignKey("user.id"), primary_key=True)
    accepted = Column(Boolean, default=False)


class DraftCollab(Base):
    __tablename__ = "draft_collab"

    slug = Column(String, nullable=True, comment="Slug")
    title = Column(String, nullable=True, comment="Title")
    subtitle = Column(String, nullable=True, comment="Subtitle")
    layout = Column(String, nullable=True, comment="Layout format")
    body = Column(String, nullable=True, comment="Body")
    cover = Column(String, nullable=True, comment="Cover")
    authors = relationship(lambda: User, secondary=DraftAuthor.__tablename__)
    topics = relationship(lambda: Topic, secondary=DraftTopic.__tablename__)
    createdAt = Column(DateTime, default=datetime.now, comment="Created At")
    updatedAt = Column(DateTime, default=datetime.now, comment="Updated At")
    chat = Column(String, unique=True, nullable=True)