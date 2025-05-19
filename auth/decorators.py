from functools import wraps
from typing import Callable, Any, Dict, Optional
from graphql import GraphQLError, GraphQLResolveInfo
from sqlalchemy import exc

from auth.credentials import AuthCredentials
from services.db import local_session
from auth.orm import Author
from auth.exceptions import OperationNotAllowed
from utils.logger import root_logger as logger
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST, SESSION_TOKEN_HEADER, SESSION_COOKIE_NAME
from auth.sessions import SessionManager
from auth.jwtcodec import JWTCodec, InvalidToken, ExpiredToken
from auth.tokenstorage import TokenStorage
from services.redis import redis
from auth.internal import authenticate

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
        # Первый приоритет: scope из ASGI (самый надежный источник)
        if hasattr(request, "scope") and isinstance(request.scope, dict):
            scope_headers = request.scope.get("headers", [])
            if scope_headers:
                headers.update({
                    k.decode("utf-8").lower(): v.decode("utf-8")
                    for k, v in scope_headers
                })
                logger.debug(f"[decorators] Получены заголовки из request.scope: {len(headers)}")
        
        # Второй приоритет: метод headers() или атрибут headers
        if hasattr(request, "headers"):
            if callable(request.headers):
                h = request.headers()
                if h:
                    headers.update({k.lower(): v for k, v in h.items()})
                    logger.debug(f"[decorators] Получены заголовки из request.headers() метода: {len(headers)}")
            else:
                h = request.headers
                if hasattr(h, "items") and callable(h.items):
                    headers.update({k.lower(): v for k, v in h.items()})
                    logger.debug(f"[decorators] Получены заголовки из request.headers атрибута: {len(headers)}")
                elif isinstance(h, dict):
                    headers.update({k.lower(): v for k, v in h.items()})
                    logger.debug(f"[decorators] Получены заголовки из request.headers словаря: {len(headers)}")
        
        # Третий приоритет: атрибут _headers
        if hasattr(request, "_headers") and request._headers:
            headers.update({k.lower(): v for k, v in request._headers.items()})
            logger.debug(f"[decorators] Получены заголовки из request._headers: {len(headers)}")
            
    except Exception as e:
        logger.warning(f"[decorators] Ошибка при доступе к заголовкам: {e}")
    
    return headers


def get_auth_token(request: Any) -> Optional[str]:
    """
    Извлекает токен авторизации из запроса.
    Порядок проверки:
    1. Проверяет auth из middleware
    2. Проверяет auth из scope 
    3. Проверяет заголовок Authorization
    4. Проверяет cookie с именем auth_token
    
    Args:
        request: Объект запроса
        
    Returns:
        Optional[str]: Токен авторизации или None
    """
    try:
        # 1. Проверяем auth из middleware (если middleware уже обработал токен)
        if hasattr(request, "auth") and request.auth:
            token = getattr(request.auth, "token", None)
            if token:
                logger.debug(f"[decorators] Токен получен из request.auth: {len(token)}")
                return token

        # 2. Проверяем наличие auth в scope
        if hasattr(request, "scope") and isinstance(request.scope, dict) and "auth" in request.scope:
            auth_info = request.scope.get("auth", {})
            if isinstance(auth_info, dict) and "token" in auth_info:
                token = auth_info["token"]
                logger.debug(f"[decorators] Токен получен из request.scope['auth']: {len(token)}")
                return token

        # 3. Проверяем заголовок Authorization
        headers = get_safe_headers(request)
        
        # Сначала проверяем основной заголовок авторизации
        auth_header = headers.get(SESSION_TOKEN_HEADER.lower(), "")
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                logger.debug(f"[decorators] Токен получен из заголовка {SESSION_TOKEN_HEADER}: {len(token)}")
                return token
            else:
                token = auth_header.strip()
                logger.debug(f"[decorators] Прямой токен получен из заголовка {SESSION_TOKEN_HEADER}: {len(token)}")
                return token
        
        # Затем проверяем стандартный заголовок Authorization, если основной не определен
        if SESSION_TOKEN_HEADER.lower() != "authorization":
            auth_header = headers.get("authorization", "")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                logger.debug(f"[decorators] Токен получен из заголовка Authorization: {len(token)}")
                return token

        # 4. Проверяем cookie
        if hasattr(request, "cookies") and request.cookies:
            token = request.cookies.get(SESSION_COOKIE_NAME)
            if token:
                logger.debug(f"[decorators] Токен получен из cookie {SESSION_COOKIE_NAME}: {len(token)}")
                return token

        # Если токен не найден ни в одном из мест
        logger.debug("[decorators] Токен авторизации не найден")
        return None
    except Exception as e:
        logger.warning(f"[decorators] Ошибка при извлечении токена: {e}")
        return None


async def validate_graphql_context(info: Any) -> None:
    """
    Проверяет валидность GraphQL контекста и проверяет авторизацию.
    
    Args:
        info: GraphQL информация о контексте
    
    Raises:
        GraphQLError: если контекст невалиден или пользователь не авторизован
    """
    # Проверка базовой структуры контекста
    if info is None or not hasattr(info, "context"):
        logger.error("[decorators] Missing GraphQL context information")
        raise GraphQLError("Internal server error: missing context")

    request = info.context.get("request")
    if not request:
        logger.error("[decorators] Missing request in context")
        raise GraphQLError("Internal server error: missing request")

    # Проверяем auth из контекста - если уже авторизован, просто возвращаем
    auth = getattr(request, "auth", None)
    if auth and auth.logged_in:
        logger.debug(f"[decorators] Пользователь уже авторизован: {auth.author_id}")
        return
        
    # Если аутентификации нет в request.auth, пробуем получить ее из scope
    if hasattr(request, "scope") and "auth" in request.scope:
        auth_cred = request.scope.get("auth")
        if isinstance(auth_cred, AuthCredentials) and auth_cred.logged_in:
            logger.debug(f"[decorators] Пользователь авторизован через scope: {auth_cred.author_id}")
            # В этом случае мы не делаем return, чтобы также проверить токен если нужно
        
    # Если авторизации нет ни в auth, ни в scope, пробуем получить и проверить токен
    token = get_auth_token(request)
    if not token:
        # Если токен не найден, возвращаем ошибку авторизации
        client_info = {
            "ip": getattr(request.client, "host", "unknown") if hasattr(request, "client") else "unknown",
            "headers": get_safe_headers(request)
        }
        logger.warning(f"[decorators] Токен авторизации не найден: {client_info}")
        raise GraphQLError("Unauthorized - please login")
    
    # Используем единый механизм проверки токена из auth.internal
    auth_state = await authenticate(request)
    
    if not auth_state.logged_in:
        error_msg = auth_state.error or "Invalid or expired token"
        logger.warning(f"[decorators] Недействительный токен: {error_msg}")
        raise GraphQLError(f"Unauthorized - {error_msg}")
    
    # Если все проверки пройдены, оставляем AuthState в scope
    # AuthenticationMiddleware извлечет нужные данные оттуда при необходимости
    logger.debug(f"[decorators] Токен успешно проверен для пользователя {auth_state.author_id}")
    return


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
            await validate_graphql_context(info)
            auth = info.context["request"].auth

            with local_session() as session:
                try:
                    # Преобразуем author_id в int для совместимости с базой данных
                    author_id = int(auth.author_id) if auth and auth.author_id else None
                    if not author_id:
                        logger.error(f"[admin_auth_required] ID автора не определен: {auth}")
                        raise GraphQLError("Unauthorized - invalid user ID")
                        
                    author = session.query(Author).filter(Author.id == author_id).one()
                    
                    if author.email in ADMIN_EMAILS:
                        logger.info(f"Admin access granted for {author.email} (ID: {author.id})")
                        return await resolver(root, info, **kwargs)
                    
                    logger.warning(f"Admin access denied for {author.email} (ID: {author.id})")
                    raise GraphQLError("Unauthorized - not an admin")
                except exc.NoResultFound:
                    logger.error(f"[admin_auth_required] Пользователь с ID {auth.author_id} не найден в базе данных")
                    raise GraphQLError("Unauthorized - user not found")

        except Exception as e:
            error_msg = str(e)
            if not isinstance(e, GraphQLError):
                error_msg = f"Admin access error: {error_msg}"
                logger.error(f"Error in admin_auth_required: {error_msg}")
            raise GraphQLError(error_msg)

    return wrapper




def permission_required(resource: str, operation: str, func):
    """
    Декоратор для проверки разрешений.

    Args:
        resource (str): Ресурс для проверки
        operation (str): Операция для проверки
        func: Декорируемая функция
    """

    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        auth: AuthCredentials = info.context["request"].auth
        if not auth.logged_in:
            raise OperationNotAllowed(auth.error_message or "Please login")

        with local_session() as session:
            author = session.query(Author).filter(Author.id == auth.author_id).one()

            # Проверяем базовые условия
            if not author.is_active:
                raise OperationNotAllowed("Account is not active")
            if author.is_locked():
                raise OperationNotAllowed("Account is locked")

            # Проверяем разрешение
            if not author.has_permission(resource, operation):
                raise OperationNotAllowed(f"No permission for {operation} on {resource}")

        return await func(parent, info, *args, **kwargs)

    return wrap



def login_accepted(func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        auth: AuthCredentials = info.context["request"].auth

        if auth and auth.logged_in:
            with local_session() as session:
                author = session.query(Author).filter(Author.id == auth.author_id).one()
                info.context["author"] = author.dict()
                info.context["user_id"] = author.id
        else:
            info.context["author"] = None
            info.context["user_id"] = None

        return await func(parent, info, *args, **kwargs)

    return wrap
