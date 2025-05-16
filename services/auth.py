from functools import wraps
from typing import Tuple

from cache.cache import get_cached_author_by_user_id
from resolvers.stat import get_with_stat
from utils.logger import root_logger as logger
from auth.internal import verify_internal_auth
from sqlalchemy import exc
from services.db import local_session
from auth.orm import Author, Role

# Список разрешенных заголовков
ALLOWED_HEADERS = ["Authorization", "Content-Type"]


async def check_auth(req) -> Tuple[str, list[str]]:
    """
    Проверка авторизации пользователя.

    Проверяет токен и получает данные из локальной БД.

    Параметры:
    - req: Входящий GraphQL запрос, содержащий заголовок авторизации.

    Возвращает:
    - user_id: str - Идентификатор пользователя
    - user_roles: list[str] - Список ролей пользователя
    """
    # Проверяем наличие токена
    token = req.headers.get("Authorization")
    if not token:
        return "", []

    # Очищаем токен от префикса Bearer если он есть
    if token.startswith("Bearer "):
        token = token.split("Bearer ")[-1].strip()

    logger.debug(f"Checking auth token: {token[:10]}...")

    # Проверяем авторизацию внутренним механизмом
    logger.debug("Using internal authentication")
    return await verify_internal_auth(token)


async def add_user_role(user_id: str, roles: list[str] = None):
    """
    Добавление ролей пользователю в локальной БД.

    Args:
        user_id: ID пользователя
        roles: Список ролей для добавления. По умолчанию ["author", "reader"]
    """
    if not roles:
        roles = ["author", "reader"]

    logger.info(f"Adding roles {roles} to user {user_id}")

    logger.debug("Using local authentication")
    with local_session() as session:
        try:
            author = session.query(Author).filter(Author.id == user_id).one()

            # Получаем существующие роли
            existing_roles = set(role.name for role in author.roles)

            # Добавляем новые роли
            for role_name in roles:
                if role_name not in existing_roles:
                    # Получаем или создаем роль
                    role = session.query(Role).filter(Role.name == role_name).first()
                    if not role:
                        role = Role(id=role_name, name=role_name)
                        session.add(role)

                    # Добавляем роль автору
                    author.roles.append(role)

            session.commit()
            return user_id

        except exc.NoResultFound:
            logger.error(f"Author {user_id} not found")
            return None


def login_required(f):
    """Декоратор для проверки авторизации пользователя."""

    @wraps(f)
    async def decorated_function(*args, **kwargs):
        info = args[1]
        req = info.context.get("request")
        user_id, user_roles = await check_auth(req)
        if user_id and user_roles:
            logger.info(f" got {user_id} roles: {user_roles}")
            info.context["user_id"] = user_id.strip()
            info.context["roles"] = user_roles
            author = await get_cached_author_by_user_id(user_id, get_with_stat)
            if not author:
                logger.error(f"author profile not found for user {user_id}")
            info.context["author"] = author
        return await f(*args, **kwargs)

    return decorated_function


def login_accepted(f):
    """Декоратор для добавления данных авторизации в контекст."""

    @wraps(f)
    async def decorated_function(*args, **kwargs):
        info = args[1]
        req = info.context.get("request")

        logger.debug("login_accepted: Проверка авторизации пользователя.")
        user_id, user_roles = await check_auth(req)
        logger.debug(f"login_accepted: user_id={user_id}, user_roles={user_roles}")

        if user_id and user_roles:
            logger.info(f"login_accepted: Пользователь авторизован: {user_id} с ролями {user_roles}")
            info.context["user_id"] = user_id.strip()
            info.context["roles"] = user_roles

            # Пробуем получить профиль автора
            author = await get_cached_author_by_user_id(user_id, get_with_stat)
            if author:
                logger.debug(f"login_accepted: Найден профиль автора: {author}")
                info.context["author"] = author.dict()
            else:
                logger.error(
                    f"login_accepted: Профиль автора не найден для пользователя {user_id}. Используем базовые данные."
                )
        else:
            logger.debug("login_accepted: Пользователь не авторизован. Очищаем контекст.")
            info.context["user_id"] = None
            info.context["roles"] = None
            info.context["author"] = None

        return await f(*args, **kwargs)

    return decorated_function
