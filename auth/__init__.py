from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from auth.sessions import SessionManager
from auth.internal import verify_internal_auth
from auth.orm import Author
from services.db import local_session
from utils.logger import root_logger as logger
from settings import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_MAX_AGE,
)


async def logout(request: Request):
    """
    Выход из системы с удалением сессии и cookie.
    """
    # Получаем токен из cookie или заголовка
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Проверяем заголовок авторизации
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Отрезаем "Bearer "

    # Если токен найден, отзываем его
    if token:
        try:
            # Декодируем токен для получения user_id
            user_id, _ = await verify_internal_auth(token)
            if user_id:
                # Отзываем сессию
                await SessionManager.revoke_session(user_id, token)
                logger.info(f"[auth] logout: Токен успешно отозван для пользователя {user_id}")
            else:
                logger.warning("[auth] logout: Не удалось получить user_id из токена")
        except Exception as e:
            logger.error(f"[auth] logout: Ошибка при отзыве токена: {e}")

    # Создаем ответ с редиректом на страницу входа
    response = RedirectResponse(url="/")

    # Удаляем cookie с токеном
    response.delete_cookie(SESSION_COOKIE_NAME)
    logger.info("[auth] logout: Cookie успешно удалена")

    return response


async def refresh_token(request: Request):
    """
    Обновление токена аутентификации.
    """
    # Получаем текущий токен из cookie или заголовка
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Отрезаем "Bearer "

    if not token:
        return JSONResponse({"success": False, "error": "Токен не найден"}, status_code=401)

    try:
        # Получаем информацию о пользователе из токена
        user_id, _ = await verify_internal_auth(token)
        if not user_id:
            return JSONResponse({"success": False, "error": "Недействительный токен"}, status_code=401)

        # Получаем пользователя из базы данных
        with local_session() as session:
            author = session.query(Author).filter(Author.id == user_id).first()

            if not author:
                return JSONResponse({"success": False, "error": "Пользователь не найден"}, status_code=404)

            # Обновляем сессию (создаем новую и отзываем старую)
            device_info = {"ip": request.client.host, "user_agent": request.headers.get("user-agent")}
            new_token = await SessionManager.refresh_session(user_id, token, device_info)

            if not new_token:
                return JSONResponse(
                    {"success": False, "error": "Не удалось обновить токен"}, status_code=500
                )

            # Создаем ответ
            response = JSONResponse(
                {
                    "success": True,
                    "token": new_token,
                    "author": {"id": author.id, "email": author.email, "name": author.name},
                }
            )

            # Устанавливаем cookie с новым токеном
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
