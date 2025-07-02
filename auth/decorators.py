from collections.abc import Callable
from functools import wraps
from typing import Any, Optional

from graphql import GraphQLError, GraphQLResolveInfo
from sqlalchemy import exc

from auth.credentials import AuthCredentials
from auth.exceptions import OperationNotAllowed
from auth.internal import authenticate
from auth.orm import Author
from orm.community import CommunityAuthor
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
    # Подробное логирование для диагностики
    logger.debug("[validate_graphql_context] Начало проверки контекста и авторизации")

    # Проверка базовой структуры контекста
    if info is None or not hasattr(info, "context"):
        logger.error("[validate_graphql_context] Missing GraphQL context information")
        msg = "Internal server error: missing context"
        raise GraphQLError(msg)

    request = info.context.get("request")
    if not request:
        logger.error("[validate_graphql_context] Missing request in context")
        msg = "Internal server error: missing request"
        raise GraphQLError(msg)

    # Логируем детали запроса
    client_info = {
        "ip": getattr(request.client, "host", "unknown") if hasattr(request, "client") else "unknown",
        "headers_keys": list(get_safe_headers(request).keys()),
    }
    logger.debug(f"[validate_graphql_context] Детали запроса: {client_info}")

    # Проверяем auth из контекста - если уже авторизован, просто возвращаем
    auth = getattr(request, "auth", None)
    if auth and getattr(auth, "logged_in", False):
        logger.debug(f"[validate_graphql_context] Пользователь уже авторизован через request.auth: {auth.author_id}")
        return

    # Если аутентификации нет в request.auth, пробуем получить ее из scope
    if hasattr(request, "scope") and "auth" in request.scope:
        auth_cred = request.scope.get("auth")
        if isinstance(auth_cred, AuthCredentials) and getattr(auth_cred, "logged_in", False):
            logger.debug(f"[validate_graphql_context] Пользователь авторизован через scope: {auth_cred.author_id}")
            return

    # Если авторизации нет ни в auth, ни в scope, пробуем получить и проверить токен
    token = get_auth_token(request)
    if not token:
        # Если токен не найден, бросаем ошибку авторизации
        client_info = {
            "ip": getattr(request.client, "host", "unknown") if hasattr(request, "client") else "unknown",
            "headers": {k: v for k, v in get_safe_headers(request).items() if k not in ["authorization", "cookie"]},
        }
        logger.warning(f"[validate_graphql_context] Токен авторизации не найден: {client_info}")
        msg = "Unauthorized - please login"
        raise GraphQLError(msg)

    # Логируем информацию о найденном токене
    logger.debug(f"[validate_graphql_context] Токен найден, длина: {len(token)}")

    # Используем единый механизм проверки токена из auth.internal
    auth_state = await authenticate(request)
    logger.debug(
        f"[validate_graphql_context] Результат аутентификации: logged_in={auth_state.logged_in}, author_id={auth_state.author_id}, error={auth_state.error}"
    )

    if not auth_state.logged_in:
        error_msg = auth_state.error or "Invalid or expired token"
        logger.warning(f"[validate_graphql_context] Недействительный токен: {error_msg}")
        msg = f"Unauthorized - {error_msg}"
        raise GraphQLError(msg)

    # Если все проверки пройдены, создаем AuthCredentials и устанавливаем в request.scope
    with local_session() as session:
        try:
            author = session.query(Author).filter(Author.id == auth_state.author_id).one()
            logger.debug(f"[validate_graphql_context] Найден автор: id={author.id}, email={author.email}")

            # Создаем объект авторизации с пустыми разрешениями
            # Разрешения будут проверяться через RBAC систему по требованию
            auth_cred = AuthCredentials(
                author_id=author.id,
                scopes={},  # Пустой словарь разрешений
                logged_in=True,
                error_message="",
                email=author.email,
                token=auth_state.token,
            )

            # Устанавливаем auth в request.scope вместо прямого присваивания к request.auth
            if hasattr(request, "scope") and isinstance(request.scope, dict):
                request.scope["auth"] = auth_cred
                logger.debug(
                    f"[validate_graphql_context] Токен успешно проверен и установлен для пользователя {auth_state.author_id}"
                )
            else:
                logger.error("[validate_graphql_context] Не удалось установить auth: отсутствует request.scope")
                msg = "Internal server error: unable to set authentication context"
                raise GraphQLError(msg)
        except exc.NoResultFound:
            logger.error(f"[validate_graphql_context] Пользователь с ID {auth_state.author_id} не найден в базе данных")
            msg = "Unauthorized - user not found"
            raise GraphQLError(msg) from None

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
    async def wrapper(root: Any = None, info: Optional[GraphQLResolveInfo] = None, **kwargs: dict[str, Any]) -> Any:
        # Подробное логирование для диагностики
        logger.debug(f"[admin_auth_required] Начало проверки авторизации для {resolver.__name__}")

        # Проверяем авторизацию пользователя
        if info is None:
            logger.error("[admin_auth_required] GraphQL info is None")
            msg = "Invalid GraphQL context"
            raise GraphQLError(msg)

        # Логируем детали запроса
        request = info.context.get("request")
        client_info = {
            "ip": getattr(request.client, "host", "unknown") if hasattr(request, "client") else "unknown",
            "headers": {k: v for k, v in get_safe_headers(request).items() if k not in ["authorization", "cookie"]},
        }
        logger.debug(f"[admin_auth_required] Детали запроса: {client_info}")

        # Проверяем наличие токена до validate_graphql_context
        token = get_auth_token(request)
        logger.debug(f"[admin_auth_required] Токен найден: {bool(token)}, длина: {len(token) if token else 0}")

        try:
            # Проверяем авторизацию - НЕ ловим GraphQLError здесь!
            await validate_graphql_context(info)
            logger.debug("[admin_auth_required] validate_graphql_context успешно пройден")
        except GraphQLError:
            # Пробрасываем GraphQLError дальше - это ошибки авторизации
            logger.debug("[admin_auth_required] GraphQLError от validate_graphql_context - пробрасываем дальше")
            raise

        # Получаем объект авторизации
        auth = None
        if hasattr(info.context["request"], "scope") and "auth" in info.context["request"].scope:
            auth = info.context["request"].scope.get("auth")
            logger.debug(f"[admin_auth_required] Auth из scope: {auth.author_id if auth else None}")
        elif hasattr(info.context["request"], "auth"):
            auth = info.context["request"].auth
            logger.debug(f"[admin_auth_required] Auth из request: {auth.author_id if auth else None}")
        else:
            logger.error("[admin_auth_required] Auth не найден ни в scope, ни в request")

        if not auth or not getattr(auth, "logged_in", False):
            logger.error("[admin_auth_required] Пользователь не авторизован после validate_graphql_context")
            msg = "Unauthorized - please login"
            raise GraphQLError(msg)

        # Проверяем, является ли пользователь администратором
        try:
            with local_session() as session:
                # Преобразуем author_id в int для совместимости с базой данных
                author_id = int(auth.author_id) if auth and auth.author_id else None
                if not author_id:
                    logger.error(f"[admin_auth_required] ID автора не определен: {auth}")
                    msg = "Unauthorized - invalid user ID"
                    raise GraphQLError(msg)

                author = session.query(Author).filter(Author.id == author_id).one()
                logger.debug(f"[admin_auth_required] Найден автор: {author.id}, {author.email}")

                # Проверяем, является ли пользователь системным администратором
                if author.email and author.email in ADMIN_EMAILS:
                    logger.info(f"System admin access granted for {author.email} (ID: {author.id})")
                    return await resolver(root, info, **kwargs)

                # Системный администратор определяется ТОЛЬКО по ADMIN_EMAILS
                logger.warning(f"System admin access denied for {author.email} (ID: {author.id}). Not in ADMIN_EMAILS.")
                msg = "Unauthorized - system admin access required"
                raise GraphQLError(msg)

        except exc.NoResultFound:
            logger.error(f"[admin_auth_required] Пользователь с ID {auth.author_id} не найден в базе данных")
            msg = "Unauthorized - user not found"
            raise GraphQLError(msg) from None
        except GraphQLError:
            # Пробрасываем GraphQLError дальше
            raise
        except Exception as e:
            # Ловим только неожиданные ошибки, не GraphQLError
            error_msg = f"Admin access error: {e!s}"
            logger.error(f"[admin_auth_required] Неожиданная ошибка: {error_msg}")
            raise GraphQLError(error_msg) from e

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
        auth = None
        if hasattr(info.context["request"], "scope") and "auth" in info.context["request"].scope:
            auth = info.context["request"].scope.get("auth")
        if not auth or not getattr(auth, "logged_in", False):
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
                ca = session.query(CommunityAuthor).filter_by(author_id=author.id, community_id=1).first()
                if ca:
                    user_roles = ca.role_list
                else:
                    user_roles = []

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
                raise OperationNotAllowed(msg) from None

    return wrap


def login_accepted(func: Callable) -> Callable:
    """
    Декоратор для проверки аутентификации пользователя.

    Args:
        func: функция-резолвер для декорирования

    Returns:
        Callable: обернутая функция
    """

    @wraps(func)
    async def wrap(parent: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any) -> Any:
        try:
            await validate_graphql_context(info)
            return await func(parent, info, *args, **kwargs)
        except GraphQLError:
            # Пробрасываем ошибки авторизации далее
            raise
        except Exception as e:
            logger.error(f"[decorators] Unexpected error in login_accepted: {e}")
            msg = "Internal server error"
            raise GraphQLError(msg) from e

    return wrap


def editor_or_admin_required(func: Callable) -> Callable:
    """
    Декоратор для проверки, что пользователь имеет роль 'editor' или 'admin'.

    Args:
        func: функция-резолвер для декорирования

    Returns:
        Callable: обернутая функция
    """

    @wraps(func)
    async def wrap(parent: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any) -> Any:
        try:
            # Сначала проверяем авторизацию
            await validate_graphql_context(info)

            # Получаем информацию о пользователе
            request = info.context.get("request")
            author_id = None

            # Пробуем получить author_id из разных источников
            if hasattr(request, "auth") and request.auth and hasattr(request.auth, "author_id"):
                author_id = request.auth.author_id
            elif hasattr(request, "scope") and "auth" in request.scope:
                auth_info = request.scope.get("auth", {})
                if isinstance(auth_info, dict):
                    author_id = auth_info.get("author_id")
                elif hasattr(auth_info, "author_id"):
                    author_id = auth_info.author_id

            if not author_id:
                logger.warning("[decorators] Не удалось получить author_id для проверки ролей")
                raise GraphQLError("Ошибка авторизации: не удалось определить пользователя")

            # Проверяем роли пользователя
            with local_session() as session:
                author = session.query(Author).filter(Author.id == author_id).first()
                if not author:
                    logger.warning(f"[decorators] Автор с ID {author_id} не найден")
                    raise GraphQLError("Пользователь не найден")

                # Проверяем email админа
                if author.email in ADMIN_EMAILS:
                    logger.debug(f"[decorators] Пользователь {author.email} является админом по email")
                    return await func(parent, info, *args, **kwargs)

                # Получаем список ролей пользователя
                ca = session.query(CommunityAuthor).filter_by(author_id=author.id, community_id=1).first()
                if ca:
                    user_roles = ca.role_list
                else:
                    user_roles = []
                logger.debug(f"[decorators] Роли пользователя {author_id}: {user_roles}")

                # Проверяем наличие роли admin или editor
                if "admin" in user_roles or "editor" in user_roles:
                    logger.debug(f"[decorators] Пользователь {author_id} имеет разрешение (роли: {user_roles})")
                    return await func(parent, info, *args, **kwargs)

                # Если нет нужных ролей
                logger.warning(f"[decorators] Пользователю {author_id} отказано в доступе. Роли: {user_roles}")
                raise GraphQLError("Доступ запрещен. Требуется роль редактора или администратора.")

        except GraphQLError:
            # Пробрасываем ошибки авторизации далее
            raise
        except Exception as e:
            logger.error(f"[decorators] Неожиданная ошибка в editor_or_admin_required: {e}")
            raise GraphQLError("Внутренняя ошибка сервера") from e

    return wrap
