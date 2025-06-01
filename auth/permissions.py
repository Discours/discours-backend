"""
Модуль для проверки разрешений пользователей в контексте сообществ.

Позволяет проверять доступ пользователя к определенным операциям в сообществе
на основе его роли в этом сообществе.
"""

from typing import Union

from sqlalchemy.orm import Session

from auth.orm import Author, Permission, Role, RolePermission
from orm.community import Community, CommunityFollower, CommunityRole
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


class ContextualPermissionCheck:
    """
    Класс для проверки контекстно-зависимых разрешений.

    Позволяет проверять разрешения пользователя в контексте сообщества,
    учитывая как глобальные роли пользователя, так и его роли внутри сообщества.
    """

    # Маппинг из ролей сообщества в системные роли RBAC
    COMMUNITY_ROLE_MAP = {
        CommunityRole.READER: "community_reader",
        CommunityRole.AUTHOR: "community_author",
        CommunityRole.EXPERT: "community_expert",
        CommunityRole.EDITOR: "community_editor",
    }

    # Обратное отображение для отображения системных ролей в роли сообщества
    RBAC_TO_COMMUNITY_ROLE = {v: k for k, v in COMMUNITY_ROLE_MAP.items()}

    @staticmethod
    def check_community_permission(
        session: Session, author_id: int, community_slug: str, resource: str, operation: str
    ) -> bool:
        """
        Проверяет наличие разрешения у пользователя в контексте сообщества.

        Args:
            session: Сессия SQLAlchemy
            author_id: ID автора/пользователя
            community_slug: Slug сообщества
            resource: Ресурс для доступа
            operation: Операция над ресурсом

        Returns:
            bool: True, если пользователь имеет разрешение, иначе False
        """
        # 1. Проверка глобальных разрешений (например, администратор)
        author = session.query(Author).filter(Author.id == author_id).one_or_none()
        if not author:
            return False

        # Если это администратор (по списку email) или у него есть глобальное разрешение
        if author.has_permission(resource, operation) or author.email in ADMIN_EMAILS:
            return True

        # 2. Проверка разрешений в контексте сообщества
        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Если автор является создателем сообщества, то у него есть полные права
        if community.created_by == author_id:
            return True

        # Получаем роли пользователя в этом сообществе
        community_follower = (
            session.query(CommunityFollower)
            .filter(CommunityFollower.author == author_id, CommunityFollower.community == community.id)
            .one_or_none()
        )

        if not community_follower or not community_follower.roles:
            # Пользователь не является членом сообщества или у него нет ролей
            return False

        # Преобразуем роли сообщества в RBAC роли
        rbac_roles = []
        community_roles = community_follower.get_roles()

        for role in community_roles:
            if role in ContextualPermissionCheck.COMMUNITY_ROLE_MAP:
                rbac_role_id = ContextualPermissionCheck.COMMUNITY_ROLE_MAP[role]
                rbac_roles.append(rbac_role_id)

        if not rbac_roles:
            return False

        # Проверяем наличие разрешения для этих ролей
        permission_id = f"{resource}:{operation}"

        # Запрос на проверку разрешений для указанных ролей
        return (
            session.query(RolePermission)
            .join(Role, Role.id == RolePermission.role)
            .join(Permission, Permission.id == RolePermission.permission)
            .filter(Role.id.in_(rbac_roles), Permission.id == permission_id)
            .first()
            is not None
        )

    @staticmethod
    def get_user_community_roles(session: Session, author_id: int, community_slug: str) -> list[CommunityRole]:
        """
        Получает список ролей пользователя в сообществе.

        Args:
            session: Сессия SQLAlchemy
            author_id: ID автора/пользователя
            community_slug: Slug сообщества

        Returns:
            List[CommunityRole]: Список ролей пользователя в сообществе
        """
        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return []

        # Если автор является создателем сообщества, то у него есть роль владельца
        if community.created_by == author_id:
            return [CommunityRole.EDITOR]  # Владелец имеет роль редактора по умолчанию

        # Получаем роли пользователя в этом сообществе
        community_follower = (
            session.query(CommunityFollower)
            .filter(CommunityFollower.author == author_id, CommunityFollower.community == community.id)
            .one_or_none()
        )

        if not community_follower or not community_follower.roles:
            return []

        return community_follower.get_roles()

    @staticmethod
    def assign_role_to_user(
        session: Session, author_id: int, community_slug: str, role: Union[CommunityRole, str]
    ) -> bool:
        """
        Назначает роль пользователю в сообществе.

        Args:
            session: Сессия SQLAlchemy
            author_id: ID автора/пользователя
            community_slug: Slug сообщества
            role: Роль для назначения (CommunityRole или строковое представление)

        Returns:
            bool: True если роль успешно назначена, иначе False
        """
        # Преобразуем строковую роль в CommunityRole если нужно
        if isinstance(role, str):
            try:
                role = CommunityRole(role)
            except ValueError:
                return False

        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Проверяем существование связи автор-сообщество
        community_follower = (
            session.query(CommunityFollower)
            .filter(CommunityFollower.author == author_id, CommunityFollower.community == community.id)
            .one_or_none()
        )

        if not community_follower:
            # Создаем новую запись CommunityFollower
            community_follower = CommunityFollower(follower=author_id, community=community.id)
            session.add(community_follower)

        # Назначаем роль
        current_roles = community_follower.get_roles() if community_follower.roles else []
        if role not in current_roles:
            current_roles.append(role)
            community_follower.set_roles(current_roles)
            session.commit()

        return True

    @staticmethod
    def revoke_role_from_user(
        session: Session, author_id: int, community_slug: str, role: Union[CommunityRole, str]
    ) -> bool:
        """
        Отзывает роль у пользователя в сообществе.

        Args:
            session: Сессия SQLAlchemy
            author_id: ID автора/пользователя
            community_slug: Slug сообщества
            role: Роль для отзыва (CommunityRole или строковое представление)

        Returns:
            bool: True если роль успешно отозвана, иначе False
        """
        # Преобразуем строковую роль в CommunityRole если нужно
        if isinstance(role, str):
            try:
                role = CommunityRole(role)
            except ValueError:
                return False

        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Проверяем существование связи автор-сообщество
        community_follower = (
            session.query(CommunityFollower)
            .filter(CommunityFollower.author == author_id, CommunityFollower.community == community.id)
            .one_or_none()
        )

        if not community_follower or not community_follower.roles:
            return False

        # Отзываем роль
        current_roles = community_follower.get_roles()
        if role in current_roles:
            current_roles.remove(role)
            community_follower.set_roles(current_roles)
            session.commit()

        return True
