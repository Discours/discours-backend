import time
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Session

from auth.identity import Password
from services.db import BaseModel as Base

# Общие table_args для всех моделей
DEFAULT_TABLE_ARGS = {"extend_existing": True}


"""
Модель закладок автора
"""


class AuthorBookmark(Base):
    """
    Закладка автора на публикацию.

    Attributes:
        author (int): ID автора
        shout (int): ID публикации
    """

    __tablename__ = "author_bookmark"
    __table_args__ = (
        Index("idx_author_bookmark_author", "author"),
        Index("idx_author_bookmark_shout", "shout"),
        {"extend_existing": True},
    )

    author = Column(ForeignKey("author.id"), primary_key=True)
    shout = Column(ForeignKey("shout.id"), primary_key=True)


class AuthorRating(Base):
    """
    Рейтинг автора от другого автора.

    Attributes:
        rater (int): ID оценивающего автора
        author (int): ID оцениваемого автора
        plus (bool): Положительная/отрицательная оценка
    """

    __tablename__ = "author_rating"
    __table_args__ = (
        Index("idx_author_rating_author", "author"),
        Index("idx_author_rating_rater", "rater"),
        {"extend_existing": True},
    )

    rater = Column(ForeignKey("author.id"), primary_key=True)
    author = Column(ForeignKey("author.id"), primary_key=True)
    plus = Column(Boolean)


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
    __table_args__ = (
        Index("idx_author_follower_author", "author"),
        Index("idx_author_follower_follower", "follower"),
        {"extend_existing": True},
    )
    id = None  # type: ignore[assignment]
    follower = Column(ForeignKey("author.id"), primary_key=True)
    author = Column(ForeignKey("author.id"), primary_key=True)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    auto = Column(Boolean, nullable=False, default=False)


class Author(Base):
    """
    Расширенная модель автора с функциями аутентификации и авторизации
    """

    __tablename__ = "author"
    __table_args__ = (
        Index("idx_author_slug", "slug"),
        Index("idx_author_email", "email"),
        Index("idx_author_phone", "phone"),
        {"extend_existing": True},
    )

    # Базовые поля автора
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True, comment="Display name")
    slug = Column(String, unique=True, comment="Author's slug")
    bio = Column(String, nullable=True, comment="Bio")  # короткое описание
    about = Column(String, nullable=True, comment="About")  # длинное форматированное описание
    pic = Column(String, nullable=True, comment="Picture")
    links = Column(JSON, nullable=True, comment="Links")

    # OAuth аккаунты - JSON с данными всех провайдеров
    # Формат: {"google": {"id": "123", "email": "user@gmail.com"}, "github": {"id": "456"}}
    oauth = Column(JSON, nullable=True, default=dict, comment="OAuth accounts data")

    # Поля аутентификации
    email = Column(String, unique=True, nullable=True, comment="Email")
    phone = Column(String, unique=True, nullable=True, comment="Phone")
    password = Column(String, nullable=True, comment="Password hash")
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(Integer, nullable=True)

    # Временные метки
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    last_seen = Column(Integer, nullable=False, default=lambda: int(time.time()))
    deleted_at = Column(Integer, nullable=True)

    oid = Column(String, nullable=True)

    # Список защищенных полей, которые видны только владельцу и администраторам
    _protected_fields = ["email", "password", "provider_access_token", "provider_refresh_token"]

    @property
    def is_authenticated(self) -> bool:
        """Проверяет, аутентифицирован ли пользователь"""
        return self.id is not None

    def verify_password(self, password: str) -> bool:
        """Проверяет пароль пользователя"""
        return Password.verify(password, str(self.password)) if self.password else False

    def set_password(self, password: str):
        """Устанавливает пароль пользователя"""
        self.password = Password.encode(password)  # type: ignore[assignment]

    def increment_failed_login(self):
        """Увеличивает счетчик неудачных попыток входа"""
        self.failed_login_attempts += 1  # type: ignore[assignment]
        if self.failed_login_attempts >= 5:
            self.account_locked_until = int(time.time()) + 300  # type: ignore[assignment] # 5 минут

    def reset_failed_login(self):
        """Сбрасывает счетчик неудачных попыток входа"""
        self.failed_login_attempts = 0  # type: ignore[assignment]
        self.account_locked_until = None  # type: ignore[assignment]

    def is_locked(self) -> bool:
        """Проверяет, заблокирован ли аккаунт"""
        if not self.account_locked_until:
            return False
        return bool(self.account_locked_until > int(time.time()))

    @property
    def username(self) -> str:
        """
        Возвращает имя пользователя для использования в токенах.
        Необходимо для совместимости с TokenStorage и JWTCodec.

        Returns:
            str: slug, email или phone пользователя
        """
        return str(self.slug or self.email or self.phone or "")

    def dict(self, access: bool = False) -> Dict[str, Any]:
        """
        Сериализует объект автора в словарь.

        Args:
            access: Если True, включает защищенные поля

        Returns:
            Dict: Словарь с данными автора
        """
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "bio": self.bio,
            "about": self.about,
            "pic": self.pic,
            "links": self.links,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_seen": self.last_seen,
            "deleted_at": self.deleted_at,
            "email_verified": self.email_verified,
        }

        # Добавляем защищенные поля только если запрошен полный доступ
        if access:
            result.update({"email": self.email, "phone": self.phone, "oauth": self.oauth})

        return result

    @classmethod
    def find_by_oauth(cls, provider: str, provider_id: str, session: Session) -> Optional["Author"]:
        """
        Находит автора по OAuth провайдеру и ID

        Args:
            provider (str): Имя OAuth провайдера (google, github и т.д.)
            provider_id (str): ID пользователя у провайдера
            session: Сессия базы данных

        Returns:
            Author или None: Найденный автор или None если не найден
        """
        # Ищем авторов, у которых есть данный провайдер с данным ID
        authors = session.query(cls).filter(cls.oauth.isnot(None)).all()
        for author in authors:
            if author.oauth and provider in author.oauth:
                oauth_data = author.oauth[provider]  # type: ignore[index]
                if isinstance(oauth_data, dict) and oauth_data.get("id") == provider_id:
                    return author
        return None

    def set_oauth_account(self, provider: str, provider_id: str, email: Optional[str] = None) -> None:
        """
        Устанавливает OAuth аккаунт для автора

        Args:
            provider (str): Имя OAuth провайдера (google, github и т.д.)
            provider_id (str): ID пользователя у провайдера
            email (Optional[str]): Email от провайдера
        """
        if not self.oauth:
            self.oauth = {}  # type: ignore[assignment]

        oauth_data: Dict[str, str] = {"id": provider_id}
        if email:
            oauth_data["email"] = email

        self.oauth[provider] = oauth_data  # type: ignore[index]

    def get_oauth_account(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Получает OAuth аккаунт провайдера

        Args:
            provider (str): Имя OAuth провайдера

        Returns:
            dict или None: Данные OAuth аккаунта или None если не найден
        """
        oauth_data = getattr(self, "oauth", None)
        if not oauth_data:
            return None
        if isinstance(oauth_data, dict):
            return oauth_data.get(provider)
        return None

    def remove_oauth_account(self, provider: str):
        """
        Удаляет OAuth аккаунт провайдера

        Args:
            provider (str): Имя OAuth провайдера
        """
        if self.oauth and provider in self.oauth:
            del self.oauth[provider]
