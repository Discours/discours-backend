import time

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from auth.orm import Author
from orm.base import BaseModel as Base


class TopicFollower(Base):
    """
    Связь между топиком и его подписчиком.

    Attributes:
        follower (int): ID подписчика
        topic (int): ID топика
        created_at (int): Время создания связи
        auto (bool): Автоматическая подписка
    """

    __tablename__ = "topic_followers"

    follower: Mapped[int] = mapped_column(ForeignKey(Author.id))
    topic: Mapped[int] = mapped_column(ForeignKey("topic.id"))
    created_at: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: int(time.time()))
    auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Определяем индексы
    __table_args__ = (
        PrimaryKeyConstraint(topic, follower),
        # Индекс для быстрого поиска всех подписчиков топика
        Index("idx_topic_followers_topic", "topic"),
        # Индекс для быстрого поиска всех топиков, на которые подписан автор
        Index("idx_topic_followers_follower", "follower"),
    )


class Topic(Base):
    """
    Модель топика (темы) публикаций.

    Attributes:
        slug (str): Уникальный строковый идентификатор темы
        title (str): Название темы
        body (str): Описание темы
        pic (str): URL изображения темы
        community (int): ID сообщества
        oid (str): Старый ID
        parent_ids (list): IDs родительских тем
    """

    __tablename__ = "topic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String, nullable=False, comment="Title")
    body: Mapped[str | None] = mapped_column(String, nullable=True, comment="Body")
    pic: Mapped[str | None] = mapped_column(String, nullable=True, comment="Picture")
    community: Mapped[int] = mapped_column(ForeignKey("community.id"), default=1)
    oid: Mapped[str | None] = mapped_column(String, nullable=True, comment="Old ID")
    parent_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True, comment="Parent Topic IDs")

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска по slug
        Index("idx_topic_slug", "slug"),
        # Индекс для быстрого поиска по сообществу
        Index("idx_topic_community", "community"),
    )
