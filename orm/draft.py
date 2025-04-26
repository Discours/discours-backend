import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from orm.author import Author
from orm.topic import Topic
from services.db import Base


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
    created_at: int = Column(Integer, nullable=False, default=lambda: int(time.time()))
    # Переименовываем колонки ID, чтобы избежать конфликта имен с relationship
    created_by: int = Column("created_by", ForeignKey("author.id"), nullable=False)
    community: int = Column("community", ForeignKey("community.id"), nullable=False, default=1)

    # optional
    layout: str = Column(String, nullable=True, default="article")
    slug: str = Column(String, unique=True)
    title: str = Column(String, nullable=True)
    subtitle: str | None = Column(String, nullable=True)
    lead: str | None = Column(String, nullable=True)
    body: str = Column(String, nullable=False, comment="Body")
    media: dict | None = Column(JSON, nullable=True)
    cover: str | None = Column(String, nullable=True, comment="Cover image url")
    cover_caption: str | None = Column(String, nullable=True, comment="Cover image alt caption")
    lang: str = Column(String, nullable=False, default="ru", comment="Language")
    seo: str | None = Column(String, nullable=True)  # JSON

    # auto
    updated_at: int | None = Column(Integer, nullable=True, index=True)
    deleted_at: int | None = Column(Integer, nullable=True, index=True)
    # Переименовываем колонки ID
    updated_by: int | None = Column("updated_by", ForeignKey("author.id"), nullable=True)
    deleted_by: int | None = Column("deleted_by", ForeignKey("author.id"), nullable=True)
    
    # --- Relationships --- 
    # Загружаем этих авторов сразу, т.к. они часто нужны и их немного (обычно 1)
    created_by = relationship("Author", foreign_keys=[created_by], lazy="joined", innerjoin=True)
    updated_by = relationship("Author", foreign_keys=[updated_by], lazy="joined")
    deleted_by = relationship("Author", foreign_keys=[deleted_by], lazy="joined")
    
    # Оставляем lazy="select" (по умолчанию) для коллекций, будем загружать их через joinedload в запросах
    authors = relationship(Author, secondary="draft_author", lazy="select")
    topics = relationship(Topic, secondary="draft_topic", lazy="select")
    
    # Связь с Community (если нужна как объект, а не ID)
    # community = relationship("Community", foreign_keys=[community_id], lazy="joined")
    # Пока оставляем community_id как ID