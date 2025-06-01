import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from auth.orm import Author
from orm.topic import Topic
from services.db import BaseModel as Base


class DraftTopic(Base):
    __tablename__ = "draft_topic"

    id = None  # type: ignore
    shout = Column(ForeignKey("draft.id"), primary_key=True, index=True)
    topic = Column(ForeignKey("topic.id"), primary_key=True, index=True)
    main = Column(Boolean, nullable=True)


class DraftAuthor(Base):
    __tablename__ = "draft_author"

    id = None  # type: ignore
    shout = Column(ForeignKey("draft.id"), primary_key=True, index=True)
    author = Column(ForeignKey("author.id"), primary_key=True, index=True)
    caption = Column(String, nullable=True, default="")


class Draft(Base):
    __tablename__ = "draft"
    # required
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    created_by = Column(ForeignKey("author.id"), nullable=False)
    community = Column(ForeignKey("community.id"), nullable=False, default=1)

    # optional
    layout = Column(String, nullable=True, default="article")
    slug = Column(String, unique=True)
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    lead = Column(String, nullable=True)
    body = Column(String, nullable=False, comment="Body")
    media = Column(JSON, nullable=True)
    cover = Column(String, nullable=True, comment="Cover image url")
    cover_caption = Column(String, nullable=True, comment="Cover image alt caption")
    lang = Column(String, nullable=False, default="ru", comment="Language")
    seo = Column(String, nullable=True)  # JSON

    # auto
    updated_at = Column(Integer, nullable=True, index=True)
    deleted_at = Column(Integer, nullable=True, index=True)
    updated_by = Column(ForeignKey("author.id"), nullable=True)
    deleted_by = Column(ForeignKey("author.id"), nullable=True)
    authors = relationship(Author, secondary="draft_author")
    topics = relationship(Topic, secondary="draft_topic")
