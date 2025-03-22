import time

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String

from services.db import Base

# from sqlalchemy_utils import TSVectorType


class AuthorRating(Base):
    """
    Рейтинг автора от другого автора.

    Attributes:
        rater (int): ID оценивающего автора
        author (int): ID оцениваемого автора
        plus (bool): Положительная/отрицательная оценка
    """

    __tablename__ = "author_rating"

    id = None  # type: ignore
    rater = Column(ForeignKey("author.id"), primary_key=True)
    author = Column(ForeignKey("author.id"), primary_key=True)
    plus = Column(Boolean)

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска всех оценок конкретного автора
        Index("idx_author_rating_author", "author"),
        # Индекс для быстрого поиска всех оценок, оставленных конкретным автором
        Index("idx_author_rating_rater", "rater"),
    )


class AuthorFollower(Base):
    """
    Подписка одного автора на другого.

    Attributes:
        follower (int): ID подписчика
        author (int): ID автора, на которого подписываются
        created_at (int): Время создания подписки
        auto (bool): Признак автоматической подписки
    """

    __tablename__ = "author_follower"

    id = None  # type: ignore
    follower = Column(ForeignKey("author.id"), primary_key=True)
    author = Column(ForeignKey("author.id"), primary_key=True)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    auto = Column(Boolean, nullable=False, default=False)

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска всех подписчиков автора
        Index("idx_author_follower_author", "author"),
        # Индекс для быстрого поиска всех авторов, на которых подписан конкретный автор
        Index("idx_author_follower_follower", "follower"),
    )


class AuthorBookmark(Base):
    """
    Закладка автора на публикацию.

    Attributes:
        author (int): ID автора
        shout (int): ID публикации
    """

    __tablename__ = "author_bookmark"

    id = None  # type: ignore
    author = Column(ForeignKey("author.id"), primary_key=True)
    shout = Column(ForeignKey("shout.id"), primary_key=True)

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска всех закладок автора
        Index("idx_author_bookmark_author", "author"),
        # Индекс для быстрого поиска всех авторов, добавивших публикацию в закладки
        Index("idx_author_bookmark_shout", "shout"),
    )


class Author(Base):
    """
    Модель автора в системе.

    Attributes:
        user (str): Идентификатор пользователя в системе авторизации
        name (str): Отображаемое имя
        slug (str): Уникальный строковый идентификатор
        bio (str): Краткая биография/статус
        about (str): Полное описание
        pic (str): URL изображения профиля
        links (dict): Ссылки на социальные сети и сайты
        created_at (int): Время создания профиля
        last_seen (int): Время последнего посещения
        updated_at (int): Время последнего обновления
        deleted_at (int): Время удаления (если профиль удален)
    """

    __tablename__ = "author"

    user = Column(String)  # unbounded link with authorizer's User type

    name = Column(String, nullable=True, comment="Display name")
    slug = Column(String, unique=True, comment="Author's slug")
    bio = Column(String, nullable=True, comment="Bio")  # status description
    about = Column(String, nullable=True, comment="About")  # long and formatted
    pic = Column(String, nullable=True, comment="Picture")
    links = Column(JSON, nullable=True, comment="Links")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    last_seen = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    deleted_at = Column(Integer, nullable=True, comment="Deleted at")

    # search_vector = Column(
    #    TSVectorType("name", "slug", "bio", "about", regconfig="pg_catalog.russian")
    # )

    # Определяем индексы
    __table_args__ = (
        # Индекс для быстрого поиска по slug
        Index("idx_author_slug", "slug"),
        # Индекс для быстрого поиска по идентификатору пользователя
        Index("idx_author_user", "user"),
        # Индекс для фильтрации неудаленных авторов
        Index("idx_author_deleted_at", "deleted_at", postgresql_where=deleted_at.is_(None)),
        # Индекс для сортировки по времени создания (для новых авторов)
        Index("idx_author_created_at", "created_at"),
        # Индекс для сортировки по времени последнего посещения
        Index("idx_author_last_seen", "last_seen"),
    )
