from typing import Optional, Tuple
import time

from sqlalchemy.orm import exc
from starlette.authentication import AuthenticationBackend, BaseUser, UnauthenticatedUser
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials
from auth.orm import Author
from auth.sessions import SessionManager
from services.db import local_session
from settings import SESSION_TOKEN_HEADER
from utils.logger import root_logger as logger


class AuthenticatedUser(BaseUser):
    """Аутентифицированный пользователь для Starlette"""

    def __init__(self, user_id: str, username: str = "", roles: list = None, permissions: dict = None):
        self.user_id = user_id
        self.username = username
        self.roles = roles or []
        self.permissions = permissions or {}

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
        Аутентифицирует пользователя по токену из заголовка.
        Токен должен быть обработан заранее AuthorizationMiddleware,
        который извлекает Bearer токен и преобразует его в чистый токен.

        Возвращает:
            tuple: (AuthCredentials, BaseUser)
        """
        if SESSION_TOKEN_HEADER not in request.headers:
            return AuthCredentials(scopes={}), UnauthenticatedUser()

        token = request.headers.get(SESSION_TOKEN_HEADER)
        if not token:
            logger.debug("[auth.authenticate] Пустой токен в заголовке")
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

                # Создаем объекты авторизации
                credentials = AuthCredentials(
                    author_id=author.id, scopes=scopes, logged_in=True, email=author.email
                )

                user = AuthenticatedUser(
                    user_id=str(author.id),
                    username=author.slug or author.email or "",
                    roles=roles,
                    permissions=scopes,
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
