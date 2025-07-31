import time
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    shout: Mapped[int] = mapped_column(ForeignKey("shout.id"), index=True)
    topic: Mapped[int] = mapped_column(ForeignKey("topic.id"), index=True)
    main: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Определяем дополнительные индексы
    __table_args__ = (
        PrimaryKeyConstraint(shout, topic),
        # Оптимизированный составной индекс для запросов, которые ищут публикации по теме
        Index("idx_shout_topic_topic_shout", "topic", "shout"),
    )


class ShoutReactionsFollower(Base):
    __tablename__ = "shout_reactions_followers"

    follower: Mapped[int] = mapped_column(ForeignKey(Author.id), index=True)
    shout: Mapped[int] = mapped_column(ForeignKey("shout.id"), index=True)
    auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(time.time()))
    deleted_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(follower, shout),
        Index("idx_shout_reactions_followers_follower", "follower"),
        Index("idx_shout_reactions_followers_shout", "shout"),
        {"extend_existing": True},
    )


class ShoutAuthor(Base):
    """
    Связь между публикацией и автором.

    Attributes:
        shout (int): ID публикации
        author (int): ID автора
        caption (str): Подпись автора
    """

    __tablename__ = "shout_author"

    shout: Mapped[int] = mapped_column(ForeignKey("shout.id"), index=True)
    author: Mapped[int] = mapped_column(ForeignKey(Author.id), index=True)
    caption: Mapped[str | None] = mapped_column(String, nullable=True, default="")

    # Определяем дополнительные индексы
    __table_args__ = (
        PrimaryKeyConstraint(shout, author),
        # Оптимизированный индекс для запросов, которые ищут публикации по автору
        Index("idx_shout_author_author_shout", "author", "shout"),
    )


class Shout(Base):
    """
    Публикация в системе.
    """

    __tablename__ = "shout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    published_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    featured_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    deleted_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    created_by: Mapped[int] = mapped_column(ForeignKey(Author.id), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey(Author.id), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey(Author.id), nullable=True)
    community: Mapped[int] = mapped_column(ForeignKey("community.id"), nullable=False)

    body: Mapped[str] = mapped_column(String, nullable=False, comment="Body")
    slug: Mapped[str | None] = mapped_column(String, unique=True)
    cover: Mapped[str | None] = mapped_column(String, nullable=True, comment="Cover image url")
    cover_caption: Mapped[str | None] = mapped_column(String, nullable=True, comment="Cover image alt caption")
    lead: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String, nullable=True)
    layout: Mapped[str] = mapped_column(String, nullable=False, default="article")
    media: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    authors = relationship(Author, secondary="shout_author")
    topics = relationship(Topic, secondary="shout_topic")
    reactions = relationship(Reaction)

    lang: Mapped[str] = mapped_column(String, nullable=False, default="ru", comment="Language")
    version_of: Mapped[int | None] = mapped_column(ForeignKey("shout.id"), nullable=True)
    oid: Mapped[str | None] = mapped_column(String, nullable=True)
    seo: Mapped[str | None] = mapped_column(String, nullable=True)  # JSON

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
