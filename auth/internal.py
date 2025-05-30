"""
Утилитные функции для внутренней аутентификации
Используются в GraphQL резолверах и декораторах
"""

import time
from typing import Any, Optional, Tuple

from sqlalchemy.orm import exc

from auth.credentials import AuthCredentials
from auth.orm import Author
from auth.sessions import SessionManager
from auth.state import AuthState
from services.db import local_session
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST
from settings import SESSION_COOKIE_NAME, SESSION_TOKEN_HEADER
from utils.logger import root_logger as logger

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


async def verify_internal_auth(token: str) -> Tuple[str, list, bool]:
    """
    Проверяет локальную авторизацию.
    Возвращает user_id, список ролей и флаг администратора.

    Args:
        token: Токен авторизации (может быть как с Bearer, так и без)

    Returns:
        tuple: (user_id, roles, is_admin)
    """
    logger.debug(f"[verify_internal_auth] Проверка токена: {token[:10]}...")

    # Обработка формата "Bearer <token>" (если токен не был обработан ранее)
    if token and token.startswith("Bearer "):
        token = token.replace("Bearer ", "", 1).strip()

    # Проверяем сессию
    payload = await SessionManager.verify_session(token)
    if not payload:
        logger.warning("[verify_internal_auth] Недействительный токен: payload не получен")
        return "", [], False

    logger.debug(f"[verify_internal_auth] Токен действителен, user_id={payload.user_id}")

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
            logger.debug(f"[verify_internal_auth] Роли пользователя: {roles}")

            # Определяем, является ли пользователь администратором
            is_admin = any(role in ["admin", "super"] for role in roles) or author.email in ADMIN_EMAILS
            logger.debug(
                f"[verify_internal_auth] Пользователь {author.id} {'является' if is_admin else 'не является'} администратором"
            )

            return str(author.id), roles, is_admin
        except exc.NoResultFound:
            logger.warning(f"[verify_internal_auth] Пользователь с ID {payload.user_id} не найден в БД или не активен")
            return "", [], False


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

    # Обновляем last_seen
    author.last_seen = int(time.time())

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

    # Если запрос имеет атрибут auth, устанавливаем в него авторизационные данные
    if hasattr(request, "auth") or hasattr(request, "__setattr__"):
        try:
            # Получаем информацию о пользователе для создания AuthCredentials
            with local_session() as session:
                author = session.query(Author).filter(Author.id == payload.user_id).one_or_none()
                if author:
                    # Получаем разрешения из ролей
                    scopes = author.get_permissions()

                    # Создаем объект авторизации
                    auth_cred = AuthCredentials(
                        author_id=author.id, scopes=scopes, logged_in=True, email=author.email, token=token
                    )

                    # Устанавливаем auth в request
                    setattr(request, "auth", auth_cred)
                    logger.debug(
                        f"[auth.authenticate] Авторизационные данные установлены в request.auth для {payload.user_id}"
                    )
        except Exception as e:
            logger.error(f"[auth.authenticate] Ошибка при установке auth в request: {e}")

    logger.info(f"[auth.authenticate] Успешная аутентификация пользователя {state.author_id}")

    return state
