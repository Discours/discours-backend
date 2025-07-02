"""
Модуль для проверки разрешений пользователей в контексте сообществ.

Позволяет проверять доступ пользователя к определенным операциям в сообществе
на основе его роли в этом сообществе.
"""

from sqlalchemy.orm import Session

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


class ContextualPermissionCheck:
    """
    Класс для проверки контекстно-зависимых разрешений.

    Позволяет проверять разрешения пользователя в контексте сообщества,
    учитывая как глобальные роли пользователя, так и его роли внутри сообщества.
    """

    @staticmethod
    async def check_community_permission(
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
        # Если это администратор (по списку email)
        if author.email in ADMIN_EMAILS:
            return True

        # 2. Проверка разрешений в контексте сообщества
        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Если автор является создателем сообщества, то у него есть полные права
        if community.created_by == author_id:
            return True

        # Проверяем наличие разрешения для этих ролей
        permission_id = f"{resource}:{operation}"
        ca = CommunityAuthor.find_by_user_and_community(author_id, community.id, session)
        return bool(await ca.has_permission(permission_id))

    @staticmethod
    async def get_user_community_roles(session: Session, author_id: int, community_slug: str) -> list[str]:
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
            return ["editor", "author", "expert", "reader"]

        ca = CommunityAuthor.find_by_user_and_community(author_id, community.id, session)
        return ca.role_list if ca else []

    @staticmethod
    async def assign_role_to_user(session: Session, author_id: int, community_slug: str, role: str) -> bool:
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

        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Проверяем существование связи автор-сообщество
        ca = CommunityAuthor.find_by_user_and_community(author_id, community.id, session)
        if not ca:
            return False

        # Назначаем роль
        ca.add_role(role)
        return True

    @staticmethod
    async def revoke_role_from_user(session: Session, author_id: int, community_slug: str, role: str) -> bool:
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

        # Получаем информацию о сообществе
        community = session.query(Community).filter(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Проверяем существование связи автор-сообщество
        ca = CommunityAuthor.find_by_user_and_community(author_id, community.id, session)
        if not ca:
            return False

        # Отзываем роль
        ca.remove_role(role)
        return True
