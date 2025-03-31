import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String

from services.db import Base


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

    id = None  # type: ignore
    follower = Column(Integer, ForeignKey("author.id"), primary_key=True)
    topic = Column(Integer, ForeignKey("topic.id"), primary_key=True)
    created_at = Column(Integer, nullable=False, default=int(time.time()))
    auto = Column(Boolean, nullable=False, default=False)

    # Определяем индексы
    __table_args__ = (
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

    slug = Column(String, unique=True)
    title = Column(String, nullable=False, comment="Title")
    body = Column(String, nullable=True, comment="Body")
    pic = Column(String, nullable=True, comment="Picture")
    community = Column(ForeignKey("community.id"), default=1)
    oid = Column(String, nullable=True, comment="Old ID")
    parent_ids = Column(JSON, nullable=True, comment="Parent Topic IDs")

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска по slug
        Index("idx_topic_slug", "slug"),
        # Индекс для быстрого поиска по сообществу
        Index("idx_topic_community", "community"),
    )
