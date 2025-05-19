from functools import wraps
from typing import Callable, Any, Dict, Optional
from graphql import GraphQLError
from services.db import local_session
from auth.orm import Author
from auth.exceptions import OperationNotAllowed
from utils.logger import root_logger as logger
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST, SESSION_COOKIE_NAME

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


def get_safe_headers(request: Any) -> Dict[str, str]:
    """
    Безопасно получает заголовки запроса.
    
    Args:
        request: Объект запроса
        
    Returns:
        Dict[str, str]: Словарь заголовков
    """
    headers = {}
    try:
        # Проверяем разные варианты доступа к заголовкам
        if hasattr(request, "_headers"):
            headers.update(request._headers)
        if hasattr(request, "headers"):
            headers.update(request.headers)
        if hasattr(request, "scope") and isinstance(request.scope, dict):
            headers.update({
                k.decode("utf-8").lower(): v.decode("utf-8")
                for k, v in request.scope.get("headers", [])
            })
    except Exception as e:
        logger.warning(f"Error accessing headers: {e}")
    return headers


def get_auth_token(request: Any) -> Optional[str]:
    """
    Извлекает токен авторизации из запроса.
    
    Args:
        request: Объект запроса
        
    Returns:
        Optional[str]: Токен авторизации или None
    """
    try:
        # Проверяем auth из middleware
        if hasattr(request, "auth") and request.auth:
            return getattr(request.auth, "token", None)

        # Проверяем заголовок
        headers = get_safe_headers(request)
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # Проверяем cookie
        if hasattr(request, "cookies"):
            return request.cookies.get(SESSION_COOKIE_NAME)

        return None
    except Exception as e:
        logger.warning(f"Error extracting auth token: {e}")
        return None


def validate_graphql_context(info: Any) -> None:
    """
    Проверяет валидность GraphQL контекста.
    
    Args:
        info: GraphQL информация о контексте
    
    Raises:
        GraphQLError: если контекст невалиден
    """
    if info is None or not hasattr(info, "context"):
        logger.error("Missing GraphQL context information")
        raise GraphQLError("Internal server error: missing context")

    request = info.context.get("request")
    if not request:
        logger.error("Missing request in context")
        raise GraphQLError("Internal server error: missing request")

    # Проверяем auth из контекста
    auth = getattr(request, "auth", None)
    if not auth or not auth.logged_in:
        # Пробуем получить токен
        token = get_auth_token(request)
        if not token:
            client_info = {
                "ip": getattr(request.client, "host", "unknown") if hasattr(request, "client") else "unknown",
                "headers": get_safe_headers(request)
            }
            logger.warning(f"No auth token found: {client_info}")
            raise GraphQLError("Unauthorized - please login")
            
        logger.warning(f"Found token but auth not initialized")
        raise GraphQLError("Unauthorized - session expired")


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
    
    Example:
        >>> @admin_auth_required
        ... async def admin_resolver(root, info, **kwargs):
        ...     return "Admin data"
    """
    @wraps(resolver)
    async def wrapper(root: Any = None, info: Any = None, **kwargs):
        try:
            validate_graphql_context(info)
            auth = info.context["request"].auth

            with local_session() as session:
                author = session.query(Author).filter(Author.id == auth.author_id).one()
                
                if author.email in ADMIN_EMAILS:
                    logger.info(f"Admin access granted for {author.email} (ID: {author.id})")
                    return await resolver(root, info, **kwargs)
                
                logger.warning(f"Admin access denied for {author.email} (ID: {author.id})")
                raise GraphQLError("Unauthorized - not an admin")

        except Exception as e:
            error_msg = str(e)
            if not isinstance(e, GraphQLError):
                error_msg = f"Admin access error: {error_msg}"
                logger.error(f"Error in admin_auth_required: {error_msg}")
            raise GraphQLError(error_msg)

    return wrapper


def require_permission(permission_string: str) -> Callable:
    """
    Декоратор для проверки наличия указанного разрешения.
    Принимает строку в формате "resource:permission".

    Args:
        permission_string: Строка в формате "resource:permission"

    Returns:
        Декоратор, проверяющий наличие указанного разрешения

    Raises:
        ValueError: если строка разрешения имеет неверный формат
    
    Example:
        >>> @require_permission("articles:edit")
        ... async def edit_article(root, info, article_id: int):
        ...     return f"Editing article {article_id}"
    """
    if not isinstance(permission_string, str) or ":" not in permission_string:
        raise ValueError('Permission string must be in format "resource:permission"')

    resource, operation = permission_string.split(":", 1)
    
    if not all([resource.strip(), operation.strip()]):
        raise ValueError("Both resource and permission must be non-empty")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(parent, info: Any = None, *args, **kwargs):
            try:
                validate_graphql_context(info)
                auth = info.context["request"].auth

                with local_session() as session:
                    author = session.query(Author).filter(Author.id == auth.author_id).one()

                    if not author.is_active:
                        raise OperationNotAllowed("Account is not active")
                    if author.is_locked():
                        raise OperationNotAllowed("Account is locked")
                    if not author.has_permission(resource, operation):
                        logger.warning(
                            f"Access denied for user {auth.author_id} - no permission {resource}:{operation}"
                        )
                        raise OperationNotAllowed(f"No permission for {operation} on {resource}")

                    return await func(parent, info, *args, **kwargs)

            except Exception as e:
                if isinstance(e, (OperationNotAllowed, GraphQLError)):
                    raise e
                logger.error(f"Error in require_permission: {e}")
                raise OperationNotAllowed(str(e))

        return wrapper

    return decorator
