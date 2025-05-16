import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from auth.orm import Author
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
    # Колонки для связей с автором
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
    updated_by: int | None = Column("updated_by", ForeignKey("author.id"), nullable=True)
    deleted_by: int | None = Column("deleted_by", ForeignKey("author.id"), nullable=True)

    # --- Relationships ---
    # Только many-to-many связи через вспомогательные таблицы
    authors = relationship(Author, secondary="draft_author", lazy="select")
    topics = relationship(Topic, secondary="draft_topic", lazy="select")

    # Связь с Community (если нужна как объект, а не ID)
    # community = relationship("Community", foreign_keys=[community_id], lazy="joined")
    # Пока оставляем community_id как ID

    # Связь с публикацией (один-к-одному или один-к-нулю)
    # Загружается через joinedload в резолвере
    publication = relationship(
        "Shout",
        primaryjoin="Draft.id == Shout.draft",
        foreign_keys="Shout.draft",
        uselist=False,
        lazy="noload",  # Не грузим по умолчанию, только через options
        viewonly=True,  # Указываем, что это связь только для чтения
    )

    def dict(self):
        """
        Сериализует объект Draft в словарь.
        Гарантирует, что поля topics и authors всегда будут списками.
        """
        return {
            "id": self.id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "community": self.community,
            "layout": self.layout,
            "slug": self.slug,
            "title": self.title,
            "subtitle": self.subtitle,
            "lead": self.lead,
            "body": self.body,
            "media": self.media or [],
            "cover": self.cover,
            "cover_caption": self.cover_caption,
            "lang": self.lang,
            "seo": self.seo,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
            "updated_by": self.updated_by,
            "deleted_by": self.deleted_by,
            # Гарантируем, что topics и authors всегда будут списками
            "topics": [topic.dict() for topic in (self.topics or [])],
            "authors": [author.dict() for author in (self.authors or [])],
        }
