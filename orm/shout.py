import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from auth.orm import Author
from orm.base import BaseModel as Base
from orm.reaction import Reaction
from orm.topic import Topic


class ShoutTopic(Base):
    """
    Связь между публикацией и темой.

    Attributes:
        shout (int): ID публикации
        topic (int): ID темы
        main (bool): Признак основной темы
    """

    __tablename__ = "shout_topic"

    id = None  # type: ignore[misc]
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

    id = None  # type: ignore[misc]
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

    id = None  # type: ignore[misc]
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
    """

    __tablename__ = "shout"

    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at = Column(Integer, nullable=True, index=True)
    published_at = Column(Integer, nullable=True, index=True)
    featured_at = Column(Integer, nullable=True, index=True)
    deleted_at = Column(Integer, nullable=True, index=True)

    created_by = Column(ForeignKey("author.id"), nullable=False)
    updated_by = Column(ForeignKey("author.id"), nullable=True)
    deleted_by = Column(ForeignKey("author.id"), nullable=True)
    community = Column(ForeignKey("community.id"), nullable=False)

    body = Column(String, nullable=False, comment="Body")
    slug = Column(String, unique=True)
    cover = Column(String, nullable=True, comment="Cover image url")
    cover_caption = Column(String, nullable=True, comment="Cover image alt caption")
    lead = Column(String, nullable=True)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    layout = Column(String, nullable=False, default="article")
    media = Column(JSON, nullable=True)

    authors = relationship(Author, secondary="shout_author")
    topics = relationship(Topic, secondary="shout_topic")
    reactions = relationship(Reaction)

    lang = Column(String, nullable=False, default="ru", comment="Language")
    version_of = Column(ForeignKey("shout.id"), nullable=True)
    oid = Column(String, nullable=True)
    seo = Column(String, nullable=True)  # JSON

    draft = Column(ForeignKey("draft.id"), nullable=True)

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
