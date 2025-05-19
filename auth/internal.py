from typing import Optional, Tuple
import time
from typing import Any

from sqlalchemy.orm import exc
from starlette.authentication import AuthenticationBackend, BaseUser, UnauthenticatedUser
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials
from auth.orm import Author
from auth.sessions import SessionManager
from services.db import local_session
from settings import SESSION_TOKEN_HEADER, SESSION_COOKIE_NAME, ADMIN_EMAILS as ADMIN_EMAILS_LIST
from utils.logger import root_logger as logger
from auth.jwtcodec import JWTCodec
from auth.exceptions import ExpiredToken, InvalidToken
from auth.state import AuthState
from auth.tokenstorage import TokenStorage
from services.redis import redis

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


class AuthenticatedUser(BaseUser):
    """Аутентифицированный пользователь для Starlette"""

    def __init__(self, 
                 user_id: str, 
                 username: str = "", 
                 roles: list = None, 
                 permissions: dict = None, 
                 token: str = None
                ):
        self.user_id = user_id
        self.username = username
        self.roles = roles or []
        self.permissions = permissions or {}
        self.token = token

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return self.user_id


class InternalAuthentication(AuthenticationBackend):
    """Внутренняя аутентификация через базу данных и Redis"""

    async def authenticate(self, request: HTTPConnection):
        """
        Аутентифицирует пользователя по токену из заголовка или cookie.
        
        Порядок поиска токена:
        1. Проверяем заголовок SESSION_TOKEN_HEADER (может быть установлен middleware)
        2. Проверяем scope/auth в request, куда middleware мог сохранить токен 
        3. Проверяем cookie

        Возвращает:
            tuple: (AuthCredentials, BaseUser)
        """
        token = None
        
        # 1. Проверяем заголовок
        if SESSION_TOKEN_HEADER in request.headers:
            token_header = request.headers.get(SESSION_TOKEN_HEADER)
            if token_header:
                if token_header.startswith("Bearer "):
                    token = token_header.replace("Bearer ", "", 1).strip()
                    logger.debug(f"[auth.authenticate] Извлечен Bearer токен из заголовка {SESSION_TOKEN_HEADER}")
                else:
                    token = token_header.strip()
                    logger.debug(f"[auth.authenticate] Извлечен прямой токен из заголовка {SESSION_TOKEN_HEADER}")
        
        # 2. Проверяем scope/auth, который мог быть установлен middleware
        if not token and hasattr(request, "scope") and "auth" in request.scope:
            auth_data = request.scope.get("auth", {})
            if isinstance(auth_data, dict) and "token" in auth_data:
                token = auth_data["token"]
                logger.debug(f"[auth.authenticate] Извлечен токен из request.scope['auth']")
        
        # 3. Проверяем cookie
        if not token and hasattr(request, "cookies") and SESSION_COOKIE_NAME in request.cookies:
            token = request.cookies.get(SESSION_COOKIE_NAME)
            logger.debug(f"[auth.authenticate] Извлечен токен из cookie {SESSION_COOKIE_NAME}")
        
        # Если токен не найден, возвращаем неаутентифицированного пользователя
        if not token:
            logger.debug("[auth.authenticate] Токен не найден")
            return AuthCredentials(scopes={}, error_message="no token"), UnauthenticatedUser()

        # Проверяем сессию в Redis
        payload = await SessionManager.verify_session(token)
        if not payload:
            logger.debug("[auth.authenticate] Недействительный токен")
            return AuthCredentials(scopes={}, error_message="Invalid token"), UnauthenticatedUser()

        with local_session() as session:
            try:
                author = (
                    session.query(Author)
                    .filter(Author.id == payload.user_id)
                    .filter(Author.is_active == True)  # noqa
                    .one()
                )

                if author.is_locked():
                    logger.debug(f"[auth.authenticate] Аккаунт заблокирован: {author.id}")
                    return AuthCredentials(
                        scopes={}, error_message="Account is locked"
                    ), UnauthenticatedUser()

                # Получаем разрешения из ролей
                scopes = author.get_permissions()

                # Получаем роли для пользователя
                roles = [role.id for role in author.roles] if author.roles else []

                # Обновляем last_seen
                author.last_seen = int(time.time())
                session.commit()

                # Создаем объекты авторизации с сохранением токена
                credentials = AuthCredentials(
                    author_id=author.id, 
                    scopes=scopes, 
                    logged_in=True, 
                    email=author.email,
                    token=token
                )

                user = AuthenticatedUser(
                    user_id=str(author.id),
                    username=author.slug or author.email or "",
                    roles=roles,
                    permissions=scopes,
                    token=token
                )

                logger.debug(f"[auth.authenticate] Успешная аутентификация: {author.email}")
                return credentials, user

            except exc.NoResultFound:
                logger.debug("[auth.authenticate] Пользователь не найден")
                return AuthCredentials(scopes={}, error_message="User not found"), UnauthenticatedUser()


async def verify_internal_auth(token: str) -> Tuple[str, list]:
    """
    Проверяет локальную авторизацию.
    Возвращает user_id и список ролей.

    Args:
        token: Токен авторизации (может быть как с Bearer, так и без)

    Returns:
        tuple: (user_id, roles)
    """
    # Обработка формата "Bearer <token>" (если токен не был обработан ранее)
    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "", 1).strip()

    # Проверяем сессию
    payload = await SessionManager.verify_session(token)
    if not payload:
        return "", []

    with local_session() as session:
        try:
            author = (
                session.query(Author)
                .filter(Author.id == payload.user_id)
                .filter(Author.is_active == True)  # noqa
                .one()
            )

            # Получаем роли
            roles = [role.id for role in author.roles]

            return str(author.id), roles
        except exc.NoResultFound:
            return "", []


async def create_internal_session(author: Author, device_info: Optional[dict] = None) -> str:
    """
    Создает новую сессию для автора

    Args:
        author: Объект автора
        device_info: Информация об устройстве (опционально)

    Returns:
        str: Токен сессии
    """
    # Сбрасываем счетчик неудачных попыток
    author.reset_failed_login()

    # Обновляем last_login
    author.last_login = int(time.time())

    # Создаем сессию, используя token для идентификации
    return await SessionManager.create_session(
        user_id=str(author.id),
        username=author.slug or author.email or author.phone or "",
        device_info=device_info,
    )


async def authenticate(request: Any) -> AuthState:
    """
    Аутентифицирует запрос по токену из разных источников.
    Порядок проверки:
    1. Проверяет токен в заголовке Authorization
    2. Проверяет токен в cookie

    Args:
        request: Запрос (обычно из middleware)

    Returns:
        AuthState: Состояние авторизации
    """
    state = AuthState()
    state.logged_in = False  # Изначально считаем, что пользователь не авторизован
    token = None

    # Проверяем наличие auth в scope (установлено middleware)
    if hasattr(request, "scope") and isinstance(request.scope, dict) and "auth" in request.scope:
        auth_info = request.scope.get("auth", {})
        if isinstance(auth_info, dict) and "token" in auth_info:
            token = auth_info["token"]
            logger.debug("[auth.authenticate] Извлечен токен из request.scope['auth']")

    # Если токен не найден в scope, проверяем заголовок
    if not token:
        try:
            headers = {}
            if hasattr(request, "headers"):
                if callable(request.headers):
                    headers = dict(request.headers())
                else:
                    headers = dict(request.headers)
                
            auth_header = headers.get(SESSION_TOKEN_HEADER, "")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                logger.debug(f"[auth.authenticate] Токен получен из заголовка {SESSION_TOKEN_HEADER}")
            elif auth_header:
                token = auth_header.strip()
                logger.debug(f"[auth.authenticate] Прямой токен получен из заголовка {SESSION_TOKEN_HEADER}")
        except Exception as e:
            logger.error(f"[auth.authenticate] Ошибка при доступе к заголовкам: {e}")

    # Если и в заголовке не найден, проверяем cookie
    if not token and hasattr(request, "cookies") and request.cookies:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            logger.debug(f"[auth.authenticate] Токен получен из cookie {SESSION_COOKIE_NAME}")

    # Если токен все еще не найден, возвращаем не авторизованное состояние
    if not token:
        logger.debug("[auth.authenticate] Токен не найден")
        return state

    # Проверяем токен через SessionManager, который теперь совместим с TokenStorage
    payload = await SessionManager.verify_session(token)
    if not payload:
        logger.warning(f"[auth.authenticate] Токен не валиден: не найдена сессия")
        state.error = "Invalid or expired token"
        return state
        
    # Создаем успешное состояние авторизации
    state.logged_in = True
    state.author_id = payload.user_id
    state.token = token
    state.username = payload.username
    
    logger.info(f"[auth.authenticate] Успешная аутентификация пользователя {state.author_id}")
    
    return state
