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

    @classmethod
    async def check_community_permission(
        cls, session: Session, author_id: int, community_slug: str, resource: str, operation: str
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
        author = session.query(Author).where(Author.id == author_id).one_or_none()
        if not author:
            return False
        # Если это администратор (по списку email)
        if author.email in ADMIN_EMAILS:
            return True

        # 2. Проверка разрешений в контексте сообщества
        # Получаем информацию о сообществе
        community = session.query(Community).where(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Если автор является создателем сообщества, то у него есть полные права
        if community.created_by == author_id:
            return True

        # Проверяем наличие разрешения для этих ролей
        permission_id = f"{resource}:{operation}"
        ca = CommunityAuthor.find_author_in_community(author_id, community.id, session)
        return bool(ca.has_permission(permission_id)) if ca else False

    @classmethod
    def get_user_community_roles(cls, session: Session, author_id: int, community_slug: str) -> list[str]:
        """
        Получает список ролей пользователя в сообществе.

        Args:
            session: Сессия SQLAlchemy
            author_id: ID автора/пользователя
            community_slug: Slug сообщества

        Returns:
            List[str]: Список ролей пользователя в сообществе
        """
        # Получаем информацию о сообществе
        community = session.query(Community).where(Community.slug == community_slug).one_or_none()
        if not community:
            return []

        # Если автор является создателем сообщества, то у него есть роль владельца
        if community.created_by == author_id:
            return ["editor", "author", "expert", "reader"]

        # Находим связь автор-сообщество
        ca = CommunityAuthor.find_author_in_community(author_id, community.id, session)
        return ca.role_list if ca else []

    @classmethod
    def check_permission(
        cls, session: Session, author_id: int, community_slug: str, resource: str, operation: str
    ) -> bool:
        """
        Проверяет наличие разрешения у пользователя в контексте сообщества.
        Синхронный метод для обратной совместимости.

        Args:
            session: Сессия SQLAlchemy
            author_id: ID автора/пользователя
            community_slug: Slug сообщества
            resource: Ресурс для доступа
            operation: Операция над ресурсом

        Returns:
            bool: True, если пользователь имеет разрешение, иначе False
        """
        # Используем тот же алгоритм, что и в асинхронной версии
        author = session.query(Author).where(Author.id == author_id).one_or_none()
        if not author:
            return False
        # Если это администратор (по списку email)
        if author.email in ADMIN_EMAILS:
            return True

        # Получаем информацию о сообществе
        community = session.query(Community).where(Community.slug == community_slug).one_or_none()
        if not community:
            return False

        # Если автор является создателем сообщества, то у него есть полные права
        if community.created_by == author_id:
            return True

        # Проверяем наличие разрешения для этих ролей
        permission_id = f"{resource}:{operation}"
        ca = CommunityAuthor.find_author_in_community(author_id, community.id, session)

        # Возвращаем результат проверки разрешения
        return bool(ca and ca.has_permission(permission_id))

    async def can_delete_community(self, user_id: int, community: Community, session: Session) -> bool:
        """
        Проверяет, может ли пользователь удалить сообщество.

        Args:
            user_id: ID пользователя
            community: Объект сообщества
            session: Сессия SQLAlchemy

        Returns:
            bool: True, если пользователь может удалить сообщество, иначе False
        """
        # Если пользователь - создатель сообщества
        if community.created_by == user_id:
            return True

        # Проверяем, есть ли у пользователя роль администратора или редактора
        author = session.query(Author).where(Author.id == user_id).first()
        if not author:
            return False

        # Проверка по email (глобальные администраторы)
        if author.email in ADMIN_EMAILS:
            return True

        # Проверка ролей в сообществе
        community_author = CommunityAuthor.find_author_in_community(user_id, community.id, session)
        if community_author:
            return "admin" in community_author.role_list or "editor" in community_author.role_list

        return False
