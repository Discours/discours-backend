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


async def check_auth(req) -> Tuple[str, list[str], bool]:
    """
    Проверка авторизации пользователя.

    Проверяет токен и получает данные из локальной БД.

    Параметры:
    - req: Входящий GraphQL запрос, содержащий заголовок авторизации.

    Возвращает:
    - user_id: str - Идентификатор пользователя
    - user_roles: list[str] - Список ролей пользователя
    - is_admin: bool - Флаг наличия у пользователя административных прав
    """
    # Проверяем наличие токена
    token = req.headers.get("Authorization")
    if not token:
        return "", [], False

    # Очищаем токен от префикса Bearer если он есть
    if token.startswith("Bearer "):
        token = token.split("Bearer ")[-1].strip()

    logger.debug(f"Checking auth token: {token[:10]}...")

    # Проверяем авторизацию внутренним механизмом
    logger.debug("Using internal authentication")
    user_id, user_roles = await verify_internal_auth(token)
    
    # Проверяем наличие административных прав у пользователя
    is_admin = False
    if user_id:
        # Быстрая проверка на админ роли в кэше
        admin_roles = ['admin', 'super']
        for role in user_roles:
            if role in admin_roles:
                is_admin = True
                break
                
        # Если в ролях нет админа, но есть ID - проверяем в БД
        if not is_admin:
            try:
                with local_session() as session:
                    # Преобразуем user_id в число
                    try:
                        user_id_int = int(user_id.strip())
                    except (ValueError, TypeError):
                        logger.error(f"Невозможно преобразовать user_id {user_id} в число")
                    else:
                        # Проверяем наличие админских прав через БД
                        from auth.orm import AuthorRole
                        admin_role = session.query(AuthorRole).filter(
                            AuthorRole.author == user_id_int,
                            AuthorRole.role.in_(["admin", "super"])
                        ).first()
                        is_admin = admin_role is not None
            except Exception as e:
                logger.error(f"Ошибка при проверке прав администратора: {e}")
    
    return user_id, user_roles, is_admin

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
    """Декоратор для проверки авторизации пользователя. Требуется наличие роли 'reader'."""

    @wraps(f)
    async def decorated_function(*args, **kwargs):
        from graphql.error import GraphQLError

        info = args[1]
        req = info.context.get("request")
        user_id, user_roles, is_admin = await check_auth(req)
        
        if not user_id:
            raise GraphQLError("Требуется авторизация")
            
        # Проверяем наличие роли reader
        if 'reader' not in user_roles and not is_admin:
            logger.error(f"Пользователь {user_id} не имеет роли 'reader'")
            raise GraphQLError("У вас нет необходимых прав для доступа")
            
        logger.info(f"Авторизован пользователь {user_id} с ролями: {user_roles}")
        info.context["user_id"] = user_id.strip()
        info.context["roles"] = user_roles
        
        # Проверяем права администратора
        info.context["is_admin"] = is_admin
        
        author = await get_cached_author_by_user_id(user_id, get_with_stat)
        if not author:
            logger.error(f"Профиль автора не найден для пользователя {user_id}")
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
        user_id, user_roles, is_admin = await check_auth(req)
        logger.debug(f"login_accepted: user_id={user_id}, user_roles={user_roles}")

        if user_id and user_roles:
            logger.info(f"login_accepted: Пользователь авторизован: {user_id} с ролями {user_roles}")
            info.context["user_id"] = user_id.strip()
            info.context["roles"] = user_roles
            
            # Проверяем права администратора
            info.context["is_admin"] = is_admin

            # Пробуем получить профиль автора
            author = await get_cached_author_by_user_id(user_id, get_with_stat)
            if author:
                logger.debug(f"login_accepted: Найден профиль автора: {author}")
                # Используем флаг is_admin из контекста или передаем права владельца для собственных данных
                is_owner = True  # Пользователь всегда является владельцем собственного профиля
                info.context["author"] = author.dict(access=is_owner or is_admin)
            else:
                logger.error(
                    f"login_accepted: Профиль автора не найден для пользователя {user_id}. Используем базовые данные."
                )
        else:
            logger.debug("login_accepted: Пользователь не авторизован. Очищаем контекст.")
            info.context["user_id"] = None
            info.context["roles"] = None
            info.context["author"] = None
            info.context["is_admin"] = False

        return await f(*args, **kwargs)

    return decorated_function

def author_required(f):
    """Декоратор для проверки наличия роли 'author' у пользователя."""

    @wraps(f)
    async def decorated_function(*args, **kwargs):
        from graphql.error import GraphQLError

        info = args[1]
        req = info.context.get("request")
        user_id, user_roles, is_admin = await check_auth(req)
        
        if not user_id:
            raise GraphQLError("Требуется авторизация")
            
        # Проверяем наличие роли author
        if 'author' not in user_roles and not is_admin:
            logger.error(f"Пользователь {user_id} не имеет роли 'author'")
            raise GraphQLError("Для выполнения этого действия необходимы права автора")
            
        logger.info(f"Авторизован автор {user_id} с ролями: {user_roles}")
        info.context["user_id"] = user_id.strip()
        info.context["roles"] = user_roles
        
        # Проверяем права администратора
        info.context["is_admin"] = is_admin
        
        author = await get_cached_author_by_user_id(user_id, get_with_stat)
        if not author:
            logger.error(f"Профиль автора не найден для пользователя {user_id}")
        info.context["author"] = author
            
        return await f(*args, **kwargs)

    return decorated_function
