import time
from typing import Dict, Set

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from auth.identity import Password
from services.db import Base

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

    id = None  # type: ignore
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

    id = None  # type: ignore
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

    id = None  # type: ignore
    follower = Column(ForeignKey("author.id"), primary_key=True)
    author = Column(ForeignKey("author.id"), primary_key=True)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    auto = Column(Boolean, nullable=False, default=False)


class RolePermission(Base):
    """Связь роли с разрешениями"""

    __tablename__ = "role_permission"
    __table_args__ = {"extend_existing": True}

    id = None
    role = Column(ForeignKey("role.id"), primary_key=True, index=True)
    permission = Column(ForeignKey("permission.id"), primary_key=True, index=True)


class Permission(Base):
    """Модель разрешения в системе RBAC"""

    __tablename__ = "permission"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, unique=True, nullable=False, default=None)
    resource = Column(String, nullable=False)
    operation = Column(String, nullable=False)


class Role(Base):
    """Модель роли в системе RBAC"""

    __tablename__ = "role"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, unique=True, nullable=False, default=None)
    name = Column(String, nullable=False)
    permissions = relationship(Permission, secondary="role_permission", lazy="joined")


class AuthorRole(Base):
    """Связь автора с ролями"""

    __tablename__ = "author_role"
    __table_args__ = {"extend_existing": True}

    id = None
    community = Column(ForeignKey("community.id"), primary_key=True, index=True, default=1)
    author = Column(ForeignKey("author.id"), primary_key=True, index=True)
    role = Column(ForeignKey("role.id"), primary_key=True, index=True)


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

    # Дополнительные поля из User
    oauth = Column(String, nullable=True, comment="OAuth provider")
    oid = Column(String, nullable=True, comment="OAuth ID")
    muted = Column(Boolean, default=False, comment="Is author muted")

    # Поля аутентификации
    email = Column(String, unique=True, nullable=True, comment="Email")
    phone = Column(String, unique=True, nullable=True, comment="Phone")
    password = Column(String, nullable=True, comment="Password hash")
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(Integer, nullable=True)

    # Временные метки
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    updated_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    last_seen = Column(Integer, nullable=False, default=lambda: int(time.time()))
    deleted_at = Column(Integer, nullable=True)

    # Связи с ролями
    roles = relationship(Role, secondary="author_role", lazy="joined")

    # search_vector = Column(
    #    TSVectorType("name", "slug", "bio", "about", regconfig="pg_catalog.russian")
    # )

    # Список защищенных полей, которые видны только владельцу и администраторам
    _protected_fields = ["email", "password", "provider_access_token", "provider_refresh_token"]

    @property
    def is_authenticated(self) -> bool:
        """Проверяет, аутентифицирован ли пользователь"""
        return self.id is not None

    def get_permissions(self) -> Dict[str, Set[str]]:
        """Получает все разрешения пользователя"""
        permissions: Dict[str, Set[str]] = {}
        for role in self.roles:
            for permission in role.permissions:
                if permission.resource not in permissions:
                    permissions[permission.resource] = set()
                permissions[permission.resource].add(permission.operation)
        return permissions

    def has_permission(self, resource: str, operation: str) -> bool:
        """Проверяет наличие разрешения у пользователя"""
        permissions = self.get_permissions()
        return resource in permissions and operation in permissions[resource]

    def verify_password(self, password: str) -> bool:
        """Проверяет пароль пользователя"""
        return Password.verify(password, self.password) if self.password else False

    def set_password(self, password: str):
        """Устанавливает пароль пользователя"""
        self.password = Password.encode(password)

    def increment_failed_login(self):
        """Увеличивает счетчик неудачных попыток входа"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.account_locked_until = int(time.time()) + 300  # 5 минут

    def reset_failed_login(self):
        """Сбрасывает счетчик неудачных попыток входа"""
        self.failed_login_attempts = 0
        self.account_locked_until = None

    def is_locked(self) -> bool:
        """Проверяет, заблокирован ли аккаунт"""
        if not self.account_locked_until:
            return False
        return self.account_locked_until > int(time.time())

    @property
    def username(self) -> str:
        """
        Возвращает имя пользователя для использования в токенах.
        Необходимо для совместимости с TokenStorage и JWTCodec.

        Returns:
            str: slug, email или phone пользователя
        """
        return self.slug or self.email or self.phone or ""

    def dict(self, access=False) -> Dict:
        """
        Сериализует объект Author в словарь с учетом прав доступа.

        Args:
            access (bool, optional): Флаг, указывающий, доступны ли защищенные поля

        Returns:
            dict: Словарь с атрибутами Author, отфильтрованный по правам доступа
        """
        # Получаем все атрибуты объекта
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}

        # Добавляем роли как список идентификаторов и названий
        if hasattr(self, "roles"):
            result["roles"] = []
            for role in self.roles:
                if isinstance(role, dict):
                    result["roles"].append(role.get("id"))

        # скрываем защищенные поля
        if not access:
            for field in self._protected_fields:
                if field in result:
                    result[field] = None

        return result
