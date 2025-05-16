from functools import wraps
from typing import Callable, Any
from graphql import GraphQLError
from services.db import local_session
from auth.orm import Author
from auth.exceptions import OperationNotAllowed
from utils.logger import root_logger as logger
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


def admin_auth_required(resolver: Callable) -> Callable:
    """
    Декоратор для защиты админских эндпоинтов.
    Проверяет принадлежность к списку разрешенных email-адресов.

    Args:
        resolver: GraphQL резолвер для защиты

    Returns:
        Обернутый резолвер, который проверяет права доступа

    Raises:
        GraphQLError: если пользователь не авторизован или не имеет доступа администратора
    """

    @wraps(resolver)
    async def wrapper(root: Any = None, info: Any = None, **kwargs):
        try:
            # Проверяем наличие info и контекста
            if info is None or not hasattr(info, "context"):
                logger.error("Missing GraphQL context information")
                raise GraphQLError("Internal server error: missing context")

            # Получаем ID пользователя из контекста запроса
            request = info.context.get("request")
            if not request or not hasattr(request, "auth"):
                logger.error("Missing request or auth object in context")
                raise GraphQLError("Internal server error: missing auth")

            auth = request.auth
            if not auth or not auth.logged_in:
                client_info = {
                    "ip": request.client.host if hasattr(request, "client") else "unknown",
                    "headers": dict(request.headers),
                }
                logger.error(f"Unauthorized access attempt for admin endpoint: {client_info}")
                raise GraphQLError("Unauthorized")

            # Проверяем принадлежность к списку админов
            with local_session() as session:
                try:
                    author = session.query(Author).filter(Author.id == auth.author_id).one()

                    # Проверка по email
                    if author.email in ADMIN_EMAILS:
                        logger.info(
                            f"Admin access granted for {author.email} (special admin, ID: {author.id})"
                        )
                        return await resolver(root, info, **kwargs)
                    else:
                        logger.warning(
                            f"Admin access denied for {author.email} (ID: {author.id}) - not in admin list"
                        )
                        raise GraphQLError("Unauthorized - not an admin")
                except Exception as db_error:
                    logger.error(f"Error fetching author with ID {auth.author_id}: {str(db_error)}")
                    raise GraphQLError("Unauthorized - user not found")

        except Exception as e:
            # Если ошибка уже GraphQLError, просто перебрасываем её
            if isinstance(e, GraphQLError):
                logger.error(f"GraphQL error in admin_auth_required: {str(e)}")
                raise e

            # Иначе, создаем новую GraphQLError
            logger.error(f"Error in admin_auth_required: {str(e)}")
            raise GraphQLError(f"Admin access error: {str(e)}")

    return wrapper


def require_permission(permission_string: str):
    """
    Декоратор для проверки наличия указанного разрешения.
    Принимает строку в формате "resource:permission".

    Args:
        permission_string: Строка в формате "resource:permission"

    Returns:
        Декоратор, проверяющий наличие указанного разрешения

    Raises:
        ValueError: если строка разрешения имеет неверный формат
    """
    if ":" not in permission_string:
        raise ValueError('Permission string must be in format "resource:permission"')

    resource, operation = permission_string.split(":", 1)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(parent, info: Any = None, *args, **kwargs):
            # Проверяем наличие info и контекста
            if info is None or not hasattr(info, "context"):
                logger.error("Missing GraphQL context information in require_permission")
                raise OperationNotAllowed("Internal server error: missing context")

            auth = info.context["request"].auth
            if not auth or not auth.logged_in:
                raise OperationNotAllowed("Unauthorized - please login")

            with local_session() as session:
                try:
                    author = session.query(Author).filter(Author.id == auth.author_id).one()

                    # Проверяем базовые условия
                    if not author.is_active:
                        raise OperationNotAllowed("Account is not active")
                    if author.is_locked():
                        raise OperationNotAllowed("Account is locked")

                    # Проверяем разрешение
                    if not author.has_permission(resource, operation):
                        logger.warning(
                            f"Access denied for user {auth.author_id} - no permission {resource}:{operation}"
                        )
                        raise OperationNotAllowed(f"No permission for {operation} on {resource}")

                    # Пользователь аутентифицирован и имеет необходимое разрешение
                    return await func(parent, info, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in require_permission: {e}")
                    if isinstance(e, OperationNotAllowed):
                        raise e
                    raise OperationNotAllowed(str(e))

        return wrapper

    return decorator
