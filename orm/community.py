import time
from typing import Any, Dict

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint, distinct, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from auth.orm import Author
from services.db import BaseModel
from services.rbac import get_permissions_for_role

# Словарь названий ролей
role_names = {
    "reader": "Читатель",
    "author": "Автор",
    "artist": "Художник",
    "expert": "Эксперт",
    "editor": "Редактор",
    "admin": "Администратор",
}

# Словарь описаний ролей
role_descriptions = {
    "reader": "Может читать и комментировать",
    "author": "Может создавать публикации",
    "artist": "Может быть credited artist",
    "expert": "Может добавлять доказательства",
    "editor": "Может модерировать контент",
    "admin": "Полные права",
}


class CommunityFollower(BaseModel):
    """
    Простая подписка пользователя на сообщество.

    Использует обычный id как первичный ключ для простоты и производительности.
    Уникальность обеспечивается индексом по (community, follower).
    """

    __tablename__ = "community_follower"

    # Простые поля - стандартный подход
    community = Column(ForeignKey("community.id"), nullable=False, index=True)
    follower = Column(ForeignKey("author.id"), nullable=False, index=True)
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))

    # Уникальность по паре сообщество-подписчик
    __table_args__ = (
        UniqueConstraint("community", "follower", name="uq_community_follower"),
        {"extend_existing": True},
    )

    def __init__(self, community: int, follower: int) -> None:
        self.community = community  # type: ignore[assignment]
        self.follower = follower  # type: ignore[assignment]


class Community(BaseModel):
    __tablename__ = "community"

    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    desc = Column(String, nullable=False, default="")
    pic = Column(String, nullable=False, default="")
    created_at = Column(Integer, nullable=False, default=lambda: int(time.time()))
    created_by = Column(ForeignKey("author.id"), nullable=False)
    settings = Column(JSON, nullable=True)
    updated_at = Column(Integer, nullable=True)
    deleted_at = Column(Integer, nullable=True)
    private = Column(Boolean, default=False)

    followers = relationship("Author", secondary="community_follower")
    created_by_author = relationship("Author", foreign_keys=[created_by])

    @hybrid_property
    def stat(self):
        return CommunityStats(self)

    def is_followed_by(self, author_id: int) -> bool:
        """Проверяет, подписан ли пользователь на сообщество"""
        from services.db import local_session

        with local_session() as session:
            follower = (
                session.query(CommunityFollower)
                .filter(CommunityFollower.community == self.id, CommunityFollower.follower == author_id)
                .first()
            )
            return follower is not None

    def get_user_roles(self, user_id: int) -> list[str]:
        """
        Получает роли пользователя в данном сообществе через CommunityAuthor

        Args:
            user_id: ID пользователя

        Returns:
            Список ролей пользователя в сообществе
        """
        from services.db import local_session

        with local_session() as session:
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.community_id == self.id, CommunityAuthor.author_id == user_id)
                .first()
            )

            return community_author.role_list if community_author else []

    def has_user_role(self, user_id: int, role_id: str) -> bool:
        """
        Проверяет, есть ли у пользователя указанная роль в этом сообществе

        Args:
            user_id: ID пользователя
            role_id: ID роли

        Returns:
            True если роль есть, False если нет
        """
        user_roles = self.get_user_roles(user_id)
        return role_id in user_roles

    def add_user_role(self, user_id: int, role: str) -> None:
        """
        Добавляет роль пользователю в сообществе

        Args:
            user_id: ID пользователя
            role: Название роли
        """
        from services.db import local_session

        with local_session() as session:
            # Ищем существующую запись
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.community_id == self.id, CommunityAuthor.author_id == user_id)
                .first()
            )

            if community_author:
                # Добавляем роль к существующей записи
                community_author.add_role(role)
            else:
                # Создаем новую запись
                community_author = CommunityAuthor(community_id=self.id, author_id=user_id, roles=role)
                session.add(community_author)

            session.commit()

    def remove_user_role(self, user_id: int, role: str) -> None:
        """
        Удаляет роль у пользователя в сообществе

        Args:
            user_id: ID пользователя
            role: Название роли
        """
        from services.db import local_session

        with local_session() as session:
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.community_id == self.id, CommunityAuthor.author_id == user_id)
                .first()
            )

            if community_author:
                community_author.remove_role(role)

                # Если ролей не осталось, удаляем запись
                if not community_author.role_list:
                    session.delete(community_author)

                session.commit()

    def set_user_roles(self, user_id: int, roles: list[str]) -> None:
        """
        Устанавливает полный список ролей пользователя в сообществе

        Args:
            user_id: ID пользователя
            roles: Список ролей для установки
        """
        from services.db import local_session

        with local_session() as session:
            # Ищем существующую запись
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.community_id == self.id, CommunityAuthor.author_id == user_id)
                .first()
            )

            if community_author:
                if roles:
                    # Обновляем роли
                    community_author.set_roles(roles)
                else:
                    # Если ролей нет, удаляем запись
                    session.delete(community_author)
            elif roles:
                # Создаем новую запись, если есть роли
                community_author = CommunityAuthor(community_id=self.id, author_id=user_id)
                community_author.set_roles(roles)
                session.add(community_author)

            session.commit()

    def get_community_members(self, with_roles: bool = False) -> list[dict[str, Any]]:
        """
        Получает список участников сообщества

        Args:
            with_roles: Если True, включает информацию о ролях

        Returns:
            Список участников с информацией о ролях
        """
        from services.db import local_session

        with local_session() as session:
            community_authors = session.query(CommunityAuthor).filter(CommunityAuthor.community_id == self.id).all()

            members = []
            for ca in community_authors:
                member_info = {
                    "author_id": ca.author_id,
                    "joined_at": ca.joined_at,
                }

                if with_roles:
                    member_info["roles"] = ca.role_list  # type: ignore[assignment]
                    # Получаем разрешения синхронно
                    try:
                        import asyncio

                        member_info["permissions"] = asyncio.run(ca.get_permissions())  # type: ignore[assignment]
                    except Exception:
                        # Если не удается получить разрешения асинхронно, используем пустой список
                        member_info["permissions"] = []  # type: ignore[assignment]

                members.append(member_info)

            return members

    def assign_default_roles_to_user(self, user_id: int) -> None:
        """
        Назначает дефолтные роли новому пользователю в сообществе

        Args:
            user_id: ID пользователя
        """
        default_roles = self.get_default_roles()
        self.set_user_roles(user_id, default_roles)

    def get_default_roles(self) -> list[str]:
        """
        Получает список дефолтных ролей для новых пользователей в сообществе

        Returns:
            Список ID ролей, которые назначаются новым пользователям по умолчанию
        """
        if not self.settings:
            return ["reader", "author"]  # По умолчанию базовые роли

        return self.settings.get("default_roles", ["reader", "author"])

    def set_default_roles(self, roles: list[str]) -> None:
        """
        Устанавливает дефолтные роли для новых пользователей в сообществе

        Args:
            roles: Список ID ролей для назначения по умолчанию
        """
        if not self.settings:
            self.settings = {}  # type: ignore[assignment]

        self.settings["default_roles"] = roles  # type: ignore[index]

    async def initialize_role_permissions(self) -> None:
        """
        Инициализирует права ролей для сообщества из дефолтных настроек.
        Вызывается при создании нового сообщества.
        """
        from services.rbac import initialize_community_permissions

        await initialize_community_permissions(int(self.id))

    def get_available_roles(self) -> list[str]:
        """
        Получает список доступных ролей в сообществе

        Returns:
            Список ID ролей, которые могут быть назначены в этом сообществе
        """
        if not self.settings:
            return ["reader", "author", "artist", "expert", "editor", "admin"]  # Все стандартные роли

        return self.settings.get("available_roles", ["reader", "author", "artist", "expert", "editor", "admin"])

    def set_available_roles(self, roles: list[str]) -> None:
        """
        Устанавливает список доступных ролей в сообществе

        Args:
            roles: Список ID ролей, доступных в сообществе
        """
        if not self.settings:
            self.settings = {}  # type: ignore[assignment]

        self.settings["available_roles"] = roles  # type: ignore[index]

    def set_slug(self, slug: str) -> None:
        """Устанавливает slug сообщества"""
        self.slug = slug  # type: ignore[assignment]


class CommunityStats:
    def __init__(self, community) -> None:
        self.community = community

    @property
    def shouts(self):
        from orm.shout import Shout

        return self.community.session.query(func.count(Shout.id)).filter(Shout.community == self.community.id).scalar()

    @property
    def followers(self):
        return (
            self.community.session.query(func.count(CommunityFollower.follower))
            .filter(CommunityFollower.community == self.community.id)
            .scalar()
        )

    @property
    def authors(self):
        from orm.shout import Shout

        # author has a shout with community id and its featured_at is not null
        return (
            self.community.session.query(func.count(distinct(Author.id)))
            .join(Shout)
            .filter(
                Shout.community == self.community.id,
                Shout.featured_at.is_not(None),
                Author.id.in_(Shout.authors),
            )
            .scalar()
        )


class CommunityAuthor(BaseModel):
    """
    Связь автора с сообществом и его ролями.

    Attributes:
        id: Уникальный ID записи
        community_id: ID сообщества
        author_id: ID автора
        roles: CSV строка с ролями (например: "reader,author,editor")
        joined_at: Время присоединения к сообществу (unix timestamp)
    """

    __tablename__ = "community_author"

    id = Column(Integer, primary_key=True)
    community_id = Column(Integer, ForeignKey("community.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("author.id"), nullable=False)
    roles = Column(Text, nullable=True, comment="Roles (comma-separated)")
    joined_at = Column(Integer, nullable=False, default=lambda: int(time.time()))

    # Связи
    community = relationship("Community", foreign_keys=[community_id])
    author = relationship("Author", foreign_keys=[author_id])

    # Уникальность по сообществу и автору
    __table_args__ = (
        Index("idx_community_author_community", "community_id"),
        Index("idx_community_author_author", "author_id"),
        UniqueConstraint("community_id", "author_id", name="uq_community_author"),
        {"extend_existing": True},
    )

    @property
    def role_list(self) -> list[str]:
        """Получает список ролей как список строк"""
        return [role.strip() for role in self.roles.split(",") if role.strip()] if self.roles else []

    @role_list.setter
    def role_list(self, value: list[str]) -> None:
        """Устанавливает список ролей из списка строк"""
        self.roles = ",".join(value) if value else None  # type: ignore[assignment]

    def has_role(self, role: str) -> bool:
        """
        Проверяет наличие роли у автора в сообществе

        Args:
            role: Название роли для проверки

        Returns:
            True если роль есть, False если нет
        """
        return role in self.role_list

    def add_role(self, role: str) -> None:
        """
        Добавляет роль автору (если её ещё нет)

        Args:
            role: Название роли для добавления
        """
        roles = self.role_list
        if role not in roles:
            roles.append(role)
            self.role_list = roles

    def remove_role(self, role: str) -> None:
        """
        Удаляет роль у автора

        Args:
            role: Название роли для удаления
        """
        roles = self.role_list
        if role in roles:
            roles.remove(role)
            self.role_list = roles

    def set_roles(self, roles: list[str]) -> None:
        """
        Устанавливает полный список ролей (заменяет текущие)

        Args:
            roles: Список ролей для установки
        """
        self.role_list = roles

    async def get_permissions(self) -> list[str]:
        """
        Получает все разрешения автора на основе его ролей в конкретном сообществе

        Returns:
            Список разрешений (permissions)
        """

        all_permissions = set()
        for role in self.role_list:
            role_perms = await get_permissions_for_role(role, int(self.community_id))
            all_permissions.update(role_perms)

        return list(all_permissions)

    def has_permission(self, permission: str) -> bool:
        """
        Проверяет наличие разрешения у автора

        Args:
            permission: Разрешение для проверки (например: "shout:create")

        Returns:
            True если разрешение есть, False если нет
        """
        return permission in self.role_list

    def dict(self, access: bool = False) -> dict[str, Any]:
        """
        Сериализует объект в словарь

        Args:
            access: Если True, включает дополнительную информацию

        Returns:
            Словарь с данными объекта
        """
        result = {
            "id": self.id,
            "community_id": self.community_id,
            "author_id": self.author_id,
            "roles": self.role_list,
            "joined_at": self.joined_at,
        }

        if access:
            # Note: permissions должны быть получены заранее через await
            # Здесь мы не можем использовать await в sync методе
            result["permissions"] = []  # Placeholder - нужно получить асинхронно

        return result

    @classmethod
    def get_user_communities_with_roles(cls, author_id: int, session=None) -> list[Dict[str, Any]]:
        """
        Получает все сообщества пользователя с его ролями

        Args:
            author_id: ID автора
            session: Сессия БД (опционально)

        Returns:
            Список словарей с информацией о сообществах и ролях
        """
        from services.db import local_session

        if session is None:
            with local_session() as ssession:
                return cls.get_user_communities_with_roles(author_id, ssession)

        community_authors = session.query(cls).filter(cls.author_id == author_id).all()

        return [
            {
                "community_id": ca.community_id,
                "roles": ca.role_list,
                "permissions": [],  # Нужно получить асинхронно
                "joined_at": ca.joined_at,
            }
            for ca in community_authors
        ]

    @classmethod
    def find_by_user_and_community(cls, author_id: int, community_id: int, session=None) -> "CommunityAuthor | None":
        """
        Находит запись CommunityAuthor по ID автора и сообщества

        Args:
            author_id: ID автора
            community_id: ID сообщества
            session: Сессия БД (опционально)

        Returns:
            CommunityAuthor или None
        """
        from services.db import local_session

        if session is None:
            with local_session() as ssession:
                return cls.find_by_user_and_community(author_id, community_id, ssession)

        return session.query(cls).filter(cls.author_id == author_id, cls.community_id == community_id).first()

    @classmethod
    def get_users_with_role(cls, community_id: int, role: str, session=None) -> list[int]:
        """
        Получает список ID пользователей с указанной ролью в сообществе

        Args:
            community_id: ID сообщества
            role: Название роли
            session: Сессия БД (опционально)

        Returns:
            Список ID пользователей
        """
        from services.db import local_session

        if session is None:
            with local_session() as ssession:
                return cls.get_users_with_role(community_id, role, ssession)

        community_authors = session.query(cls).filter(cls.community_id == community_id).all()

        return [ca.author_id for ca in community_authors if ca.has_role(role)]

    @classmethod
    def get_community_stats(cls, community_id: int, session=None) -> Dict[str, Any]:
        """
        Получает статистику ролей в сообществе

        Args:
            community_id: ID сообщества
            session: Сессия БД (опционально)

        Returns:
            Словарь со статистикой ролей
        """
        from services.db import local_session

        if session is None:
            with local_session() as s:
                return cls.get_community_stats(community_id, s)

        community_authors = session.query(cls).filter(cls.community_id == community_id).all()

        role_counts: dict[str, int] = {}
        total_members = len(community_authors)

        for ca in community_authors:
            for role in ca.role_list:
                role_counts[role] = role_counts.get(role, 0) + 1

        return {
            "total_members": total_members,
            "role_counts": role_counts,
            "roles_distribution": {
                role: count / total_members if total_members > 0 else 0 for role, count in role_counts.items()
            },
        }


# === HELPER ФУНКЦИИ ДЛЯ РАБОТЫ С РОЛЯМИ ===


def get_user_roles_in_community(author_id: int, community_id: int = 1) -> list[str]:
    """
    Удобная функция для получения ролей пользователя в сообществе

    Args:
        author_id: ID автора
        community_id: ID сообщества (по умолчанию 1)

    Returns:
        Список ролей пользователя
    """
    from services.db import local_session

    with local_session() as session:
        ca = CommunityAuthor.find_by_user_and_community(author_id, community_id, session)
        return ca.role_list if ca else []


async def check_user_permission_in_community(author_id: int, permission: str, community_id: int = 1) -> bool:
    """
    Проверяет разрешение пользователя в сообществе с учетом иерархии ролей

    Args:
        author_id: ID автора
        permission: Разрешение для проверки
        community_id: ID сообщества (по умолчанию 1)

    Returns:
        True если разрешение есть, False если нет
    """
    # Используем новую систему RBAC с иерархией
    from services.rbac import user_has_permission

    return await user_has_permission(author_id, permission, community_id)


def assign_role_to_user(author_id: int, role: str, community_id: int = 1) -> bool:
    """
    Назначает роль пользователю в сообществе

    Args:
        author_id: ID автора
        role: Название роли
        community_id: ID сообщества (по умолчанию 1)

    Returns:
        True если роль была добавлена, False если уже была
    """
    from services.db import local_session

    with local_session() as session:
        ca = CommunityAuthor.find_by_user_and_community(author_id, community_id, session)

        if ca:
            if ca.has_role(role):
                return False  # Роль уже есть
            ca.add_role(role)
        else:
            # Создаем новую запись
            ca = CommunityAuthor(community_id=community_id, author_id=author_id, roles=role)
            session.add(ca)

        session.commit()
        return True


def remove_role_from_user(author_id: int, role: str, community_id: int = 1) -> bool:
    """
    Удаляет роль у пользователя в сообществе

    Args:
        author_id: ID автора
        role: Название роли
        community_id: ID сообщества (по умолчанию 1)

    Returns:
        True если роль была удалена, False если её не было
    """
    from services.db import local_session

    with local_session() as session:
        ca = CommunityAuthor.find_by_user_and_community(author_id, community_id, session)

        if ca and ca.has_role(role):
            ca.remove_role(role)

            # Если ролей не осталось, удаляем запись
            if not ca.role_list:
                session.delete(ca)

            session.commit()
            return True

        return False


def migrate_old_roles_to_community_author():
    """
    Функция миграции для переноса ролей из старой системы в CommunityAuthor

    [непроверенное] Предполагает, что старые роли хранились в auth.orm.AuthorRole
    """
    from auth.orm import AuthorRole
    from services.db import local_session

    with local_session() as session:
        # Получаем все старые роли
        old_roles = session.query(AuthorRole).all()

        print(f"[миграция] Найдено {len(old_roles)} старых записей ролей")

        # Группируем по автору и сообществу
        user_community_roles = {}

        for role in old_roles:
            key = (role.author, role.community)
            if key not in user_community_roles:
                user_community_roles[key] = []

            # Извлекаем базовое имя роли (убираем суффикс сообщества если есть)
            role_name = role.role
            if isinstance(role_name, str) and "-" in role_name:
                base_role = role_name.split("-")[0]
            else:
                base_role = role_name

            if base_role not in user_community_roles[key]:
                user_community_roles[key].append(base_role)

        # Создаем новые записи CommunityAuthor
        migrated_count = 0
        for (author_id, community_id), roles in user_community_roles.items():
            # Проверяем, есть ли уже запись
            existing = CommunityAuthor.find_by_user_and_community(author_id, community_id, session)

            if not existing:
                ca = CommunityAuthor(community_id=community_id, author_id=author_id)
                ca.set_roles(roles)
                session.add(ca)
                migrated_count += 1
            else:
                print(f"[миграция] Запись для автора {author_id} в сообществе {community_id} уже существует")

        session.commit()
        print(f"[миграция] Создано {migrated_count} новых записей CommunityAuthor")
        print("[миграция] Миграция завершена. Проверьте результаты перед удалением старых таблиц.")


# === CRUD ОПЕРАЦИИ ДЛЯ RBAC ===


def get_all_community_members_with_roles(community_id: int = 1) -> list[dict[str, Any]]:
    """
    Получает всех участников сообщества с их ролями и разрешениями

    Args:
        community_id: ID сообщества

    Returns:
        Список участников с полной информацией
    """
    from services.db import local_session

    with local_session() as session:
        community = session.query(Community).filter(Community.id == community_id).first()

        if not community:
            return []

        return community.get_community_members(with_roles=True)


def bulk_assign_roles(user_role_pairs: list[tuple[int, str]], community_id: int = 1) -> dict[str, int]:
    """
    Массовое назначение ролей пользователям

    Args:
        user_role_pairs: Список кортежей (author_id, role)
        community_id: ID сообщества

    Returns:
        Статистика операции в формате {"success": int, "failed": int}
    """

    success_count = 0
    failed_count = 0

    for author_id, role in user_role_pairs:
        try:
            if assign_role_to_user(author_id, role, community_id):
                success_count += 1
            else:
                # Если роль уже была, считаем это успехом
                success_count += 1
        except Exception as e:
            print(f"[ошибка] Не удалось назначить роль {role} пользователю {author_id}: {e}")
            failed_count += 1

    return {"success": success_count, "failed": failed_count}
