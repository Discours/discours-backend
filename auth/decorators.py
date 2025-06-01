from collections.abc import Callable
from functools import wraps
from typing import Any, Optional

from graphql import GraphQLError, GraphQLResolveInfo
from sqlalchemy import exc

from auth.credentials import AuthCredentials
from auth.exceptions import OperationNotAllowed
from auth.internal import authenticate
from auth.orm import Author
from services.db import local_session
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST
from settings import SESSION_COOKIE_NAME, SESSION_TOKEN_HEADER
from utils.logger import root_logger as logger

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


def get_safe_headers(request: Any) -> dict[str, str]:
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
                headers.update({k.decode("utf-8").lower(): v.decode("utf-8") for k, v in scope_headers})
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


async def validate_graphql_context(info: GraphQLResolveInfo) -> None:
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
        msg = "Internal server error: missing context"
        raise GraphQLError(msg)

    request = info.context.get("request")
    if not request:
        logger.error("[decorators] Missing request in context")
        msg = "Internal server error: missing request"
        raise GraphQLError(msg)

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
            # Устанавливаем auth в request для дальнейшего использования
            request.auth = auth_cred
            return

    # Если авторизации нет ни в auth, ни в scope, пробуем получить и проверить токен
    token = get_auth_token(request)
    if not token:
        # Если токен не найден, возвращаем ошибку авторизации
        client_info = {
            "ip": getattr(request.client, "host", "unknown") if hasattr(request, "client") else "unknown",
            "headers": get_safe_headers(request),
        }
        logger.warning(f"[decorators] Токен авторизации не найден: {client_info}")
        msg = "Unauthorized - please login"
        raise GraphQLError(msg)

    # Используем единый механизм проверки токена из auth.internal
    auth_state = await authenticate(request)

    if not auth_state.logged_in:
        error_msg = auth_state.error or "Invalid or expired token"
        logger.warning(f"[decorators] Недействительный токен: {error_msg}")
        msg = f"Unauthorized - {error_msg}"
        raise GraphQLError(msg)

    # Если все проверки пройдены, создаем AuthCredentials и устанавливаем в request.auth
    with local_session() as session:
        try:
            author = session.query(Author).filter(Author.id == auth_state.author_id).one()
            # Получаем разрешения из ролей
            scopes = author.get_permissions()

            # Создаем объект авторизации
            auth_cred = AuthCredentials(
                author_id=author.id,
                scopes=scopes,
                logged_in=True,
                error_message="",
                email=author.email,
                token=auth_state.token,
            )

            # Устанавливаем auth в request
            request.auth = auth_cred
            logger.debug(f"[decorators] Токен успешно проверен и установлен для пользователя {auth_state.author_id}")
        except exc.NoResultFound:
            logger.error(f"[decorators] Пользователь с ID {auth_state.author_id} не найден в базе данных")
            msg = "Unauthorized - user not found"
            raise GraphQLError(msg)

    return


def admin_auth_required(resolver: Callable) -> Callable:
    """
    Декоратор для защиты админских эндпоинтов.
    Проверяет принадлежность к списку разрешенных email-адресов.

    Args:
        resolver: GraphQL резолвер для защиты

    Returns:
        Обернутый резолвер, который проверяет права доступа администратора

    Raises:
        GraphQLError: если пользователь не авторизован или не имеет доступа администратора

    Example:
        >>> @admin_auth_required
        ... async def admin_resolver(root, info, **kwargs):
        ...     return "Admin data"
    """

    @wraps(resolver)
    async def wrapper(root: Any = None, info: Optional[GraphQLResolveInfo] = None, **kwargs):
        try:
            # Проверяем авторизацию пользователя
            if info is None:
                logger.error("[admin_auth_required] GraphQL info is None")
                msg = "Invalid GraphQL context"
                raise GraphQLError(msg)

            await validate_graphql_context(info)
            if info:
                # Получаем объект авторизации
                auth = info.context["request"].auth
                if not auth or not auth.logged_in:
                    logger.error("[admin_auth_required] Пользователь не авторизован после validate_graphql_context")
                    msg = "Unauthorized - please login"
                    raise GraphQLError(msg)

                # Проверяем, является ли пользователь администратором
                with local_session() as session:
                    try:
                        # Преобразуем author_id в int для совместимости с базой данных
                        author_id = int(auth.author_id) if auth and auth.author_id else None
                        if not author_id:
                            logger.error(f"[admin_auth_required] ID автора не определен: {auth}")
                            msg = "Unauthorized - invalid user ID"
                            raise GraphQLError(msg)

                        author = session.query(Author).filter(Author.id == author_id).one()

                        # Проверяем, является ли пользователь администратором
                        if author.email in ADMIN_EMAILS:
                            logger.info(f"Admin access granted for {author.email} (ID: {author.id})")
                            return await resolver(root, info, **kwargs)

                        # Проверяем роли пользователя
                        admin_roles = ["admin", "super"]
                        user_roles = [role.id for role in author.roles] if author.roles else []

                        if any(role in admin_roles for role in user_roles):
                            logger.info(
                                f"Admin access granted for {author.email} (ID: {author.id}) with role: {user_roles}"
                            )
                            return await resolver(root, info, **kwargs)

                        logger.warning(f"Admin access denied for {author.email} (ID: {author.id}). Roles: {user_roles}")
                        msg = "Unauthorized - not an admin"
                        raise GraphQLError(msg)
                    except exc.NoResultFound:
                        logger.error(
                            f"[admin_auth_required] Пользователь с ID {auth.author_id} не найден в базе данных"
                        )
                        msg = "Unauthorized - user not found"
                        raise GraphQLError(msg)

        except Exception as e:
            error_msg = str(e)
            if not isinstance(e, GraphQLError):
                error_msg = f"Admin access error: {error_msg}"
                logger.error(f"Error in admin_auth_required: {error_msg}")
            raise GraphQLError(error_msg)

    return wrapper


def permission_required(resource: str, operation: str, func: Callable) -> Callable:
    """
    Декоратор для проверки разрешений.

    Args:
        resource: Ресурс для проверки
        operation: Операция для проверки
        func: Декорируемая функция
    """

    @wraps(func)
    async def wrap(parent: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any) -> Any:
        # Сначала проверяем авторизацию
        await validate_graphql_context(info)

        # Получаем объект авторизации
        logger.debug(f"[permission_required] Контекст: {info.context}")
        auth = info.context["request"].auth
        if not auth or not auth.logged_in:
            logger.error("[permission_required] Пользователь не авторизован после validate_graphql_context")
            msg = "Требуются права доступа"
            raise OperationNotAllowed(msg)

        # Проверяем разрешения
        with local_session() as session:
            try:
                author = session.query(Author).filter(Author.id == auth.author_id).one()

                # Проверяем базовые условия
                if author.is_locked():
                    msg = "Account is locked"
                    raise OperationNotAllowed(msg)

                # Проверяем, является ли пользователь администратором (у них есть все разрешения)
                if author.email in ADMIN_EMAILS:
                    logger.debug(f"[permission_required] Администратор {author.email} имеет все разрешения")
                    return await func(parent, info, *args, **kwargs)

                # Проверяем роли пользователя
                admin_roles = ["admin", "super"]
                user_roles = [role.id for role in author.roles] if author.roles else []

                if any(role in admin_roles for role in user_roles):
                    logger.debug(
                        f"[permission_required] Пользователь с ролью администратора {author.email} имеет все разрешения"
                    )
                    return await func(parent, info, *args, **kwargs)

                # Проверяем разрешение
                if not author.has_permission(resource, operation):
                    logger.warning(
                        f"[permission_required] У пользователя {author.email} нет разрешения {operation} на {resource}"
                    )
                    msg = f"No permission for {operation} on {resource}"
                    raise OperationNotAllowed(msg)

                logger.debug(
                    f"[permission_required] Пользователь {author.email} имеет разрешение {operation} на {resource}"
                )
                return await func(parent, info, *args, **kwargs)
            except exc.NoResultFound:
                logger.error(f"[permission_required] Пользователь с ID {auth.author_id} не найден в базе данных")
                msg = "User not found"
                raise OperationNotAllowed(msg)

    return wrap


def login_accepted(func: Callable) -> Callable:
    """
    Декоратор для резолверов, которые могут работать как с авторизованными,
    так и с неавторизованными пользователями.

    Добавляет информацию о пользователе в контекст, если пользователь авторизован.

    Args:
        func: Декорируемая функция
    """

    @wraps(func)
    async def wrap(parent: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any) -> Any:
        try:
            # Пробуем проверить авторизацию, но не выбрасываем исключение, если пользователь не авторизован
            try:
                await validate_graphql_context(info)
            except GraphQLError:
                # Игнорируем ошибку авторизации
                pass

            # Получаем объект авторизации
            auth = getattr(info.context["request"], "auth", None)

            if auth and auth.logged_in:
                # Если пользователь авторизован, добавляем информацию о нем в контекст
                with local_session() as session:
                    try:
                        author = session.query(Author).filter(Author.id == auth.author_id).one()
                        info.context["author"] = author.dict()
                        logger.debug(f"[login_accepted] Пользователь авторизован: {author.id}")
                    except exc.NoResultFound:
                        logger.warning(f"[login_accepted] Пользователь с ID {auth.author_id} не найден в базе данных")
                        info.context["author"] = None
            else:
                # Если пользователь не авторизован, устанавливаем пустые значения
                info.context["author"] = None
                logger.debug("[login_accepted] Пользователь не авторизован")

            return await func(parent, info, *args, **kwargs)
        except Exception as e:
            if not isinstance(e, GraphQLError):
                logger.error(f"[login_accepted] Ошибка: {e}")
            raise

    return wrap
