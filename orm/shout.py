import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from orm.author import Author
from orm.reaction import Reaction
from orm.topic import Topic
from services.db import Base


class ShoutTopic(Base):
    """
    Связь между публикацией и темой.

    Attributes:
        shout (int): ID публикации
        topic (int): ID темы
        main (bool): Признак основной темы
    """

    __tablename__ = "shout_topic"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    topic = Column(ForeignKey("topic.id"), primary_key=True, index=True)
    main = Column(Boolean, nullable=True)

    # Определяем дополнительные индексы
    __table_args__ = (
        # Оптимизированный составной индекс для запросов, которые ищут публикации по теме
        Index("idx_shout_topic_topic_shout", "topic", "shout"),
    )


class ShoutReactionsFollower(Base):
    __tablename__ = "shout_reactions_followers"

    id = None  # type: ignore
    follower = Column(ForeignKey("author.id"), primary_key=True, index=True)
    shout = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    auto = Column(Boolean, nullable=False, default=False)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    deleted_at = Column(Integer, nullable=True)


class ShoutAuthor(Base):
    """
    Связь между публикацией и автором.

    Attributes:
        shout (int): ID публикации
        author (int): ID автора
        caption (str): Подпись автора
    """

    __tablename__ = "shout_author"

    id = None  # type: ignore
    shout = Column(ForeignKey("shout.id"), primary_key=True, index=True)
    author = Column(ForeignKey("author.id"), primary_key=True, index=True)
    caption = Column(String, nullable=True, default="")

    # Определяем дополнительные индексы
    __table_args__ = (
        # Оптимизированный индекс для запросов, которые ищут публикации по автору
        Index("idx_shout_author_author_shout", "author", "shout"),
    )


class Shout(Base):
    """
    Публикация в системе.

    Attributes:
        body (str)
        slug (str)
        cover (str) : "Cover image url"
        cover_caption (str) : "Cover image alt caption"
        lead (str) 
        title (str)
        subtitle (str)
        layout (str)
        media (dict)
        authors (list[Author])
        topics (list[Topic])
        reactions (list[Reaction])
        lang (str)
        version_of (int)
        oid (str)
        seo (str) : JSON
        draft (int)
        created_at (int)
        updated_at (int)
        published_at (int)
        featured_at (int)
        deleted_at (int)
        created_by (int)
        updated_by (int)
        deleted_by (int)
        community (int)
    """

    __tablename__ = "shout"

    created_at: int = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at: int | None = Column(Integer, nullable=True, index=True)
    published_at: int | None = Column(Integer, nullable=True, index=True)
    featured_at: int | None = Column(Integer, nullable=True, index=True)
    deleted_at: int | None = Column(Integer, nullable=True, index=True)

    created_by: int = Column(ForeignKey("author.id"), nullable=False)
    updated_by: int | None = Column(ForeignKey("author.id"), nullable=True)
    deleted_by: int | None = Column(ForeignKey("author.id"), nullable=True)
    community: int = Column(ForeignKey("community.id"), nullable=False)

    body: str = Column(String, nullable=False, comment="Body")
    slug: str = Column(String, unique=True)
    cover: str | None = Column(String, nullable=True, comment="Cover image url")
    cover_caption: str | None = Column(String, nullable=True, comment="Cover image alt caption")
    lead: str | None = Column(String, nullable=True)
    title: str = Column(String, nullable=False)
    subtitle: str | None = Column(String, nullable=True)
    layout: str = Column(String, nullable=False, default="article")
    media: dict | None = Column(JSON, nullable=True)

    authors = relationship(Author, secondary="shout_author")
    topics = relationship(Topic, secondary="shout_topic")
    reactions = relationship(Reaction)

    lang: str = Column(String, nullable=False, default="ru", comment="Language")
    version_of: int | None = Column(ForeignKey("shout.id"), nullable=True)
    oid: str | None = Column(String, nullable=True)

    seo: str | None = Column(String, nullable=True)  # JSON

    draft: int | None = Column(ForeignKey("draft.id"), nullable=True)

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска неудаленных публикаций
        Index("idx_shout_deleted_at", "deleted_at", postgresql_where=deleted_at.is_(None)),
        # Индекс для быстрой фильтрации по community
        Index("idx_shout_community", "community"),
        # Индекс для быстрого поиска по slug
        Index("idx_shout_slug", "slug"),
        # Составной индекс для фильтрации опубликованных неудаленных публикаций
        Index(
            "idx_shout_published_deleted",
            "published_at",
            "deleted_at",
            postgresql_where=published_at.is_not(None) & deleted_at.is_(None),
        ),
    )
