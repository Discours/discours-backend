"""
RBAC: динамическая система прав для ролей и сообществ.

- Каталог всех сущностей и действий хранится в permissions_catalog.json
- Дефолтные права ролей — в default_role_permissions.json
- Кастомные права ролей для каждого сообщества — в Redis (ключ community:roles:{community_id})
- При создании сообщества автоматически копируются дефолтные права
- Декораторы получают роли пользователя из CommunityAuthor для конкретного сообщества
"""

import asyncio
import json
from functools import wraps
from pathlib import Path
from typing import Callable, List

from services.redis import redis
from utils.logger import root_logger as logger

# --- Загрузка каталога сущностей и дефолтных прав ---

with Path("permissions_catalog.json").open() as f:
    PERMISSIONS_CATALOG = json.load(f)

with Path("default_role_permissions.json").open() as f:
    DEFAULT_ROLE_PERMISSIONS = json.load(f)

DEFAULT_ROLES_HIERARCHY: dict[str, list[str]] = {
    "reader": [],  # Базовая роль, ничего не наследует
    "author": ["reader"],  # Наследует от reader
    "artist": ["reader", "author"],  # Наследует от reader и author
    "expert": ["reader", "author", "artist"],  # Наследует от reader и author
    "editor": ["reader", "author", "artist", "expert"],  # Наследует от reader и author
    "admin": ["reader", "author", "artist", "expert", "editor"],  # Наследует от всех
}


# --- Инициализация и управление правами сообщества ---


async def initialize_community_permissions(community_id: int) -> None:
    """
    Инициализирует права для нового сообщества на основе дефолтных настроек с учетом иерархии.

    Args:
        community_id: ID сообщества
    """
    key = f"community:roles:{community_id}"

    # Проверяем, не инициализировано ли уже
    existing = await redis.get(key)
    if existing:
        logger.debug(f"Права для сообщества {community_id} уже инициализированы")
        return

    # Создаем полные списки разрешений с учетом иерархии
    expanded_permissions = {}

    for role, direct_permissions in DEFAULT_ROLE_PERMISSIONS.items():
        # Начинаем с прямых разрешений роли
        all_permissions = set(direct_permissions)

        # Добавляем наследуемые разрешения
        inherited_roles = DEFAULT_ROLES_HIERARCHY.get(role, [])
        for inherited_role in inherited_roles:
            inherited_permissions = DEFAULT_ROLE_PERMISSIONS.get(inherited_role, [])
            all_permissions.update(inherited_permissions)

        expanded_permissions[role] = list(all_permissions)

    # Сохраняем в Redis уже развернутые списки с учетом иерархии
    await redis.set(key, json.dumps(expanded_permissions))
    logger.info(f"Инициализированы права с иерархией для сообщества {community_id}")


async def get_role_permissions_for_community(community_id: int) -> dict:
    """
    Получает права ролей для конкретного сообщества.
    Если права не настроены, автоматически инициализирует их дефолтными.

    Args:
        community_id: ID сообщества

    Returns:
        Словарь прав ролей для сообщества
    """
    key = f"community:roles:{community_id}"
    data = await redis.get(key)

    if data:
        return json.loads(data)

    # Автоматически инициализируем, если не найдено
    await initialize_community_permissions(community_id)
    return DEFAULT_ROLE_PERMISSIONS


async def set_role_permissions_for_community(community_id: int, role_permissions: dict) -> None:
    """
    Устанавливает кастомные права ролей для сообщества.

    Args:
        community_id: ID сообщества
        role_permissions: Словарь прав ролей
    """
    key = f"community:roles:{community_id}"
    await redis.set(key, json.dumps(role_permissions))
    logger.info(f"Обновлены права ролей для сообщества {community_id}")


async def get_permissions_for_role(role: str, community_id: int) -> list[str]:
    """
    Получает список разрешений для конкретной роли в сообществе.
    Иерархия уже применена при инициализации сообщества.

    Args:
        role: Название роли
        community_id: ID сообщества

    Returns:
        Список разрешений для роли
    """
    role_perms = await get_role_permissions_for_community(community_id)
    return role_perms.get(role, [])


# --- Получение ролей пользователя ---


def get_user_roles_in_community(author_id: int, community_id: int) -> list[str]:
    """
    Получает роли пользователя в конкретном сообществе из CommunityAuthor.

    Args:
        author_id: ID автора
        community_id: ID сообщества

    Returns:
        Список ролей пользователя в сообществе
    """
    try:
        from orm.community import CommunityAuthor
        from services.db import local_session

        with local_session() as session:
            ca = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )

            return ca.role_list if ca else []
    except ImportError:
        # Если есть циклический импорт, возвращаем пустой список
        return []


async def user_has_permission(author_id: int, permission: str, community_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя конкретное разрешение в сообществе.

    Args:
        author_id: ID автора
        permission: Разрешение для проверки
        community_id: ID сообщества

    Returns:
        True если разрешение есть, False если нет
    """
    user_roles = get_user_roles_in_community(author_id, community_id)
    return await roles_have_permission(user_roles, permission, community_id)


# --- Проверка прав ---
async def roles_have_permission(role_slugs: list[str], permission: str, community_id: int) -> bool:
    """
    Проверяет, есть ли у набора ролей конкретное разрешение в сообществе.

    Args:
        role_slugs: Список ролей для проверки
        permission: Разрешение для проверки
        community_id: ID сообщества

    Returns:
        True если хотя бы одна роль имеет разрешение
    """
    role_perms = await get_role_permissions_for_community(community_id)
    return any(permission in role_perms.get(role, []) for role in role_slugs)


# --- Декораторы ---
class RBACError(Exception):
    """Исключение для ошибок RBAC."""


def get_user_roles_from_context(info) -> tuple[list[str], int]:
    """
    Получение ролей пользователя из GraphQL контекста с учетом сообщества.

    Returns:
        Кортеж (роли_пользователя, community_id)
    """
    # Получаем ID автора из контекста
    author_data = getattr(info.context, "author", {})
    author_id = author_data.get("id") if isinstance(author_data, dict) else None

    if not author_id:
        return [], 1

    # Получаем community_id
    community_id = get_community_id_from_context(info)

    # Получаем роли пользователя в этом сообществе
    user_roles = get_user_roles_in_community(author_id, community_id)

    # Проверяем, является ли пользователь системным администратором
    try:
        from auth.orm import Author
        from services.db import local_session
        from settings import ADMIN_EMAILS

        admin_emails = ADMIN_EMAILS.split(",") if ADMIN_EMAILS else []

        with local_session() as session:
            author = session.query(Author).filter(Author.id == author_id).first()
            if author and author.email and author.email in admin_emails:
                # Системный администратор автоматически получает роль admin в любом сообществе
                if "admin" not in user_roles:
                    user_roles = [*user_roles, "admin"]
    except Exception:
        # Если не удалось проверить email (включая циклические импорты), продолжаем с существующими ролями
        pass

    return user_roles, community_id


def get_community_id_from_context(info) -> int:
    """
    Получение community_id из GraphQL контекста или аргументов.
    """
    # Пробуем из контекста
    community_id = getattr(info.context, "community_id", None)
    if community_id:
        return int(community_id)

    # Пробуем из аргументов resolver'а
    if hasattr(info, "variable_values") and info.variable_values:
        if "community_id" in info.variable_values:
            return int(info.variable_values["community_id"])
        if "communityId" in info.variable_values:
            return int(info.variable_values["communityId"])

    # Пробуем из прямых аргументов
    if hasattr(info, "field_asts") and info.field_asts:
        for field_ast in info.field_asts:
            if hasattr(field_ast, "arguments"):
                for arg in field_ast.arguments:
                    if arg.name.value in ["community_id", "communityId"]:
                        return int(arg.value.value)

    # Fallback: основное сообщество
    return 1


def require_permission(permission: str):
    """
    Декоратор для проверки конкретного разрешения у пользователя в сообществе.

    Args:
        permission: Требуемое разрешение (например, "shout:create")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else None
            if not info or not hasattr(info, "context"):
                raise RBACError("GraphQL info context не найден")

            user_roles, community_id = get_user_roles_from_context(info)
            if not await roles_have_permission(user_roles, permission, community_id):
                raise RBACError("Недостаточно прав в сообществе")

            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role: str):
    """
    Декоратор для проверки конкретной роли у пользователя в сообществе.

    Args:
        role: Требуемая роль (например, "admin", "editor")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else None
            if not info or not hasattr(info, "context"):
                raise RBACError("GraphQL info context не найден")

            user_roles, community_id = get_user_roles_from_context(info)
            if role not in user_roles:
                raise RBACError("Требуется роль в сообществе", role)

            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(permissions: List[str]):
    """
    Декоратор для проверки любого из списка разрешений.

    Args:
        permissions: Список разрешений, любое из которых подходит
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else None
            if not info or not hasattr(info, "context"):
                raise RBACError("GraphQL info context не найден")

            user_roles, community_id = get_user_roles_from_context(info)
            has_any = any(await roles_have_permission(user_roles, perm, community_id) for perm in permissions)
            if not has_any:
                raise RBACError("Недостаточно прав. Требуется любое из: ", permissions)

            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        return wrapper

    return decorator


def require_all_permissions(permissions: List[str]):
    """
    Декоратор для проверки всех разрешений из списка.

    Args:
        permissions: Список разрешений, все из которых требуются
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else None
            if not info or not hasattr(info, "context"):
                raise RBACError("GraphQL info context не найден")

            user_roles, community_id = get_user_roles_from_context(info)
            missing_perms = [
                perm for perm in permissions if not await roles_have_permission(user_roles, perm, community_id)
            ]

            if missing_perms:
                raise RBACError("Недостаточно прав. Отсутствуют: ", missing_perms)

            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        return wrapper

    return decorator


def admin_only(func: Callable) -> Callable:
    """
    Декоратор для ограничения доступа только администраторам сообщества.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        info = args[1] if len(args) > 1 else None
        if not info or not hasattr(info, "context"):
            raise RBACError("GraphQL info context не найден")

        user_roles, community_id = get_user_roles_from_context(info)
        if "admin" not in user_roles:
            raise RBACError("Доступ только для администраторов сообщества", community_id)

        return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

    return wrapper
