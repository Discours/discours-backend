"""
Утилитные функции для внутренней аутентификации
Используются в GraphQL резолверах и декораторах
"""

import time
from typing import Optional

from sqlalchemy.orm.exc import NoResultFound

from auth.orm import Author
from auth.state import AuthState
from auth.tokens.storage import TokenStorage as TokenManager
from orm.community import CommunityAuthor
from services.db import local_session
from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST
from utils.logger import root_logger as logger

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


async def verify_internal_auth(token: str) -> tuple[int, list, bool]:
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
    payload = await TokenManager.verify_session(token)
    if not payload:
        logger.warning("[verify_internal_auth] Недействительный токен: payload не получен")
        return 0, [], False

    logger.debug(f"[verify_internal_auth] Токен действителен, user_id={payload.user_id}")

    with local_session() as session:
        try:
            author = session.query(Author).where(Author.id == payload.user_id).one()

            # Получаем роли
            ca = session.query(CommunityAuthor).filter_by(author_id=author.id, community_id=1).first()
            roles = ca.role_list if ca else []
            logger.debug(f"[verify_internal_auth] Роли пользователя: {roles}")

            # Определяем, является ли пользователь администратором
            is_admin = any(role in ["admin", "super"] for role in roles) or author.email in ADMIN_EMAILS
            logger.debug(
                f"[verify_internal_auth] Пользователь {author.id} {'является' if is_admin else 'не является'} администратором"
            )

            return int(author.id), roles, is_admin
        except NoResultFound:
            logger.warning(f"[verify_internal_auth] Пользователь с ID {payload.user_id} не найден в БД или не активен")
            return 0, [], False


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
    author.last_seen = int(time.time())  # type: ignore[assignment]

    # Создаем сессию, используя token для идентификации
    return await TokenManager.create_session(
        user_id=str(author.id),
        username=str(author.slug or author.email or author.phone or ""),
        device_info=device_info,
    )


async def authenticate(request) -> AuthState:
    """
    Аутентифицирует пользователя по токену из запроса.

    Args:
        request: Объект запроса

    Returns:
        AuthState: Состояние аутентификации
    """
    logger.debug("[authenticate] Начало аутентификации")

    # Создаем объект AuthState
    auth_state = AuthState()
    auth_state.logged_in = False
    auth_state.author_id = None
    auth_state.error = None
    auth_state.token = None

    # Получаем токен из запроса
    token = request.headers.get("Authorization")
    if not token:
        logger.info("[authenticate] Токен не найден в запросе")
        auth_state.error = "No authentication token"
        return auth_state

    # Обработка формата "Bearer <token>" (если токен не был обработан ранее)
    if token and token.startswith("Bearer "):
        token = token.replace("Bearer ", "", 1).strip()

    logger.debug(f"[authenticate] Токен найден, длина: {len(token)}")

    # Проверяем токен
    try:
        # Используем TokenManager вместо прямого создания SessionTokenManager
        auth_result = await TokenManager.verify_session(token)

        if auth_result and hasattr(auth_result, "user_id") and auth_result.user_id:
            logger.debug(f"[authenticate] Успешная аутентификация, user_id: {auth_result.user_id}")
            auth_state.logged_in = True
            auth_state.author_id = auth_result.user_id
            auth_state.token = token
            return auth_state

        error_msg = "Invalid or expired token"
        logger.warning(f"[authenticate] Недействительный токен: {error_msg}")
        auth_state.error = error_msg
        return auth_state
    except Exception as e:
        logger.error(f"[authenticate] Ошибка при проверке токена: {e}")
        auth_state.error = f"Authentication error: {e!s}"
        return auth_state
