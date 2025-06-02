from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from auth.internal import verify_internal_auth
from auth.orm import Author
from auth.tokens.storage import TokenStorage
from services.db import local_session
from settings import (
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_TOKEN_HEADER,
)
from utils.logger import root_logger as logger


async def logout(request: Request) -> Response:
    """
    Выход из системы с удалением сессии и cookie.

    Поддерживает получение токена из:
    1. HTTP-only cookie
    2. Заголовка Authorization
    """
    token = None
    # Получаем токен из cookie
    if SESSION_COOKIE_NAME in request.cookies:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        logger.debug(f"[auth] logout: Получен токен из cookie {SESSION_COOKIE_NAME}")

    # Если токен не найден в cookie, проверяем заголовок
    if not token:
        # Сначала проверяем основной заголовок авторизации
        auth_header = request.headers.get(SESSION_TOKEN_HEADER)
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                logger.debug(f"[auth] logout: Получен Bearer токен из заголовка {SESSION_TOKEN_HEADER}")
            else:
                token = auth_header.strip()
                logger.debug(f"[auth] logout: Получен прямой токен из заголовка {SESSION_TOKEN_HEADER}")

    # Если токен не найден в основном заголовке, проверяем стандартный Authorization
    if not token and "Authorization" in request.headers:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            logger.debug("[auth] logout: Получен Bearer токен из заголовка Authorization")

    # Если токен найден, отзываем его
    if token:
        try:
            # Декодируем токен для получения user_id
            user_id, _, _ = await verify_internal_auth(token)
            if user_id:
                # Отзываем сессию
                await TokenStorage.revoke_session(token)
                logger.info(f"[auth] logout: Токен успешно отозван для пользователя {user_id}")
            else:
                logger.warning("[auth] logout: Не удалось получить user_id из токена")
        except Exception as e:
            logger.error(f"[auth] logout: Ошибка при отзыве токена: {e}")
    else:
        logger.warning("[auth] logout: Токен не найден в запросе")

    # Создаем ответ с редиректом на страницу входа
    response = RedirectResponse(url="/")

    # Удаляем cookie с токеном
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        secure=SESSION_COOKIE_SECURE,
        httponly=SESSION_COOKIE_HTTPONLY,
        samesite=SESSION_COOKIE_SAMESITE,
    )
    logger.info("[auth] logout: Cookie успешно удалена")

    return response


async def refresh_token(request: Request) -> JSONResponse:
    """
    Обновление токена аутентификации.

    Поддерживает получение токена из:
    1. HTTP-only cookie
    2. Заголовка Authorization

    Возвращает новый токен как в HTTP-only cookie, так и в теле ответа.
    """
    token = None
    source = None

    # Получаем текущий токен из cookie
    if SESSION_COOKIE_NAME in request.cookies:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        source = "cookie"
        logger.debug(f"[auth] refresh_token: Токен получен из cookie {SESSION_COOKIE_NAME}")

    # Если токен не найден в cookie, проверяем заголовок авторизации
    if not token:
        # Проверяем основной заголовок авторизации
        auth_header = request.headers.get(SESSION_TOKEN_HEADER)
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                source = "header"
                logger.debug(f"[auth] refresh_token: Токен получен из заголовка {SESSION_TOKEN_HEADER} (Bearer)")
            else:
                token = auth_header.strip()
                source = "header"
                logger.debug(f"[auth] refresh_token: Токен получен из заголовка {SESSION_TOKEN_HEADER} (прямой)")

    # Если токен не найден в основном заголовке, проверяем стандартный Authorization
    if not token and "Authorization" in request.headers:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            source = "header"
            logger.debug("[auth] refresh_token: Токен получен из заголовка Authorization")

    if not token:
        logger.warning("[auth] refresh_token: Токен не найден в запросе")
        return JSONResponse({"success": False, "error": "Токен не найден"}, status_code=401)

    try:
        # Получаем информацию о пользователе из токена
        user_id, _, _ = await verify_internal_auth(token)
        if not user_id:
            logger.warning("[auth] refresh_token: Недействительный токен")
            return JSONResponse({"success": False, "error": "Недействительный токен"}, status_code=401)

        # Получаем пользователя из базы данных
        with local_session() as session:
            author = session.query(Author).filter(Author.id == user_id).first()

            if not author:
                logger.warning(f"[auth] refresh_token: Пользователь с ID {user_id} не найден")
                return JSONResponse({"success": False, "error": "Пользователь не найден"}, status_code=404)

            # Обновляем сессию (создаем новую и отзываем старую)
            device_info = {
                "ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent"),
            }
            new_token = await TokenStorage.refresh_session(user_id, token, device_info)

            if not new_token:
                logger.error(f"[auth] refresh_token: Не удалось обновить токен для пользователя {user_id}")
                return JSONResponse({"success": False, "error": "Не удалось обновить токен"}, status_code=500)

            # Создаем ответ
            response = JSONResponse(
                {
                    "success": True,
                    # Возвращаем токен в теле ответа только если он был получен из заголовка
                    "token": new_token if source == "header" else None,
                    "author": {"id": author.id, "email": author.email, "name": author.name},
                }
            )

            # Всегда устанавливаем cookie с новым токеном
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=new_token,
                httponly=SESSION_COOKIE_HTTPONLY,
                secure=SESSION_COOKIE_SECURE,
                samesite=SESSION_COOKIE_SAMESITE,
                max_age=SESSION_COOKIE_MAX_AGE,
            )

            logger.info(f"[auth] refresh_token: Токен успешно обновлен для пользователя {user_id}")
            return response

    except Exception as e:
        logger.error(f"[auth] refresh_token: Ошибка при обновлении токена: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=401)
