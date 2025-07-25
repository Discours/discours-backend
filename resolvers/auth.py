"""
Auth резолверы - тонкие GraphQL обёртки над AuthService
"""

from typing import Any, Dict, List, Union

from graphql import GraphQLResolveInfo
from graphql.error import GraphQLError

from services.auth import auth_service
from services.schema import mutation, query, type_author
from settings import SESSION_COOKIE_NAME
from utils.logger import root_logger as logger


def handle_error(operation: str, error: Exception) -> GraphQLError:
    """Обрабатывает ошибки в резолверах"""
    logger.error(f"Ошибка при {operation}: {error}")
    return GraphQLError(f"Не удалось {operation}: {error}")


# === РЕЗОЛВЕР ДЛЯ ТИПА AUTHOR ===


@type_author.field("roles")
def resolve_roles(obj: Union[Dict, Any], info: GraphQLResolveInfo) -> List[str]:
    """Резолвер для поля roles автора"""
    try:
        if hasattr(obj, "get_roles"):
            return obj.get_roles()

        if isinstance(obj, dict):
            roles_data = obj.get("roles_data", {})
            if isinstance(roles_data, list):
                return roles_data
            if isinstance(roles_data, dict):
                return roles_data.get("1", [])

        return []
    except Exception as e:
        logger.error(f"Ошибка получения ролей: {e}")
        return []


# === МУТАЦИИ АУТЕНТИФИКАЦИИ ===


@mutation.field("registerUser")
async def register_user(
    _: None, _info: GraphQLResolveInfo, email: str, password: str = "", name: str = ""
) -> dict[str, Any]:
    """Регистрирует нового пользователя"""
    try:
        return await auth_service.register_user(email, password, name)
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
        return {"success": False, "token": None, "author": None, "error": str(e)}


@mutation.field("sendLink")
async def send_link(
    _: None, _info: GraphQLResolveInfo, email: str, lang: str = "ru", template: str = "confirm"
) -> dict[str, Any]:
    """Отправляет ссылку подтверждения"""
    try:
        result = await auth_service.send_verification_link(email, lang, template)
        return result
    except Exception as e:
        raise handle_error("отправке ссылки подтверждения", e) from e


@mutation.field("confirmEmail")
@auth_service.login_required
async def confirm_email(_: None, _info: GraphQLResolveInfo, token: str) -> dict[str, Any]:
    """Подтверждает email по токену"""
    try:
        return await auth_service.confirm_email(token)
    except Exception as e:
        logger.error(f"Ошибка подтверждения email: {e}")
        return {"success": False, "token": None, "author": None, "error": str(e)}


@mutation.field("login")
async def login(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Авторизация пользователя"""
    try:
        email = kwargs.get("email", "")
        password = kwargs.get("password", "")
        request = info.context.get("request")

        result = await auth_service.login(email, password, request)

        # Устанавливаем cookie если есть токен
        if result.get("success") and result.get("token") and request:
            try:
                from starlette.responses import JSONResponse

                if not hasattr(info.context, "response"):
                    response = JSONResponse({})
                    response.set_cookie(
                        key=SESSION_COOKIE_NAME,
                        value=result["token"],
                        httponly=True,
                        secure=True,
                        samesite="strict",
                        max_age=86400 * 30,
                    )
                    info.context["response"] = response
            except Exception as cookie_error:
                logger.warning(f"Не удалось установить cookie: {cookie_error}")

        return result
    except Exception as e:
        logger.error(f"Ошибка входа: {e}")
        return {"success": False, "token": None, "author": None, "error": str(e)}


@mutation.field("logout")
@auth_service.login_required
async def logout(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Выход из системы"""
    try:
        author = info.context.get("author")
        if not author:
            return {"success": False, "message": "Пользователь не найден в контексте"}

        user_id = str(author.get("id"))
        request = info.context.get("request")

        # Получаем токен
        token = None
        if request:
            token = request.cookies.get(SESSION_COOKIE_NAME)
            if not token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]

        result = await auth_service.logout(user_id, token)

        # Удаляем cookie
        if request and hasattr(info.context, "response"):
            try:
                info.context["response"].delete_cookie(SESSION_COOKIE_NAME)
            except Exception as e:
                logger.warning(f"Не удалось удалить cookie: {e}")

        return result
    except Exception as e:
        logger.error(f"Ошибка выхода: {e}")
        return {"success": False}


@mutation.field("refreshToken")
@auth_service.login_required
async def refresh_token(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Обновление токена"""
    try:
        author = info.context.get("author")
        if not author:
            return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

        user_id = str(author.get("id"))
        request = info.context.get("request")

        if not request:
            return {"success": False, "token": None, "author": None, "error": "Запрос не найден"}

        # Получаем токен
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return {"success": False, "token": None, "author": None, "error": "Токен не найден"}

        device_info = {
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent"),
        }

        result = await auth_service.refresh_token(user_id, token, device_info)

        # Устанавливаем новый cookie
        if result.get("success") and result.get("token"):
            try:
                if hasattr(info.context, "response"):
                    info.context["response"].set_cookie(
                        key=SESSION_COOKIE_NAME,
                        value=result["token"],
                        httponly=True,
                        secure=True,
                        samesite="strict",
                        max_age=86400 * 30,
                    )
            except Exception as e:
                logger.warning(f"Не удалось обновить cookie: {e}")

        return result
    except Exception as e:
        logger.error(f"Ошибка обновления токена: {e}")
        return {"success": False, "token": None, "author": None, "error": str(e)}


@mutation.field("requestPasswordReset")
async def request_password_reset(_: None, _info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Запрос сброса пароля"""
    try:
        email = kwargs.get("email", "")
        lang = kwargs.get("lang", "ru")
        return await auth_service.request_password_reset(email, lang)
    except Exception as e:
        logger.error(f"Ошибка запроса сброса пароля: {e}")
        return {"success": False}


@mutation.field("updateSecurity")
@auth_service.login_required
async def update_security(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Обновление пароля и email"""
    try:
        author = info.context.get("author")
        if not author:
            return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

        user_id = author.get("id")
        old_password = kwargs.get("oldPassword", "")
        new_password = kwargs.get("newPassword")
        email = kwargs.get("email")

        return await auth_service.update_security(user_id, old_password, new_password, email)
    except Exception as e:
        logger.error(f"Ошибка обновления безопасности: {e}")
        return {"success": False, "error": str(e), "author": None}


@mutation.field("confirmEmailChange")
@auth_service.login_required
async def confirm_email_change(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Подтверждение смены email по токену"""
    try:
        author = info.context.get("author")
        if not author:
            return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

        user_id = author.get("id")
        token = kwargs.get("token", "")

        return await auth_service.confirm_email_change(user_id, token)
    except Exception as e:
        logger.error(f"Ошибка подтверждения смены email: {e}")
        return {"success": False, "error": str(e), "author": None}


@mutation.field("cancelEmailChange")
@auth_service.login_required
async def cancel_email_change(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Отмена смены email"""
    try:
        author = info.context.get("author")
        if not author:
            return {"success": False, "error": "NOT_AUTHENTICATED", "author": None}

        user_id = author.get("id")
        return await auth_service.cancel_email_change(user_id)
    except Exception as e:
        logger.error(f"Ошибка отмены смены email: {e}")
        return {"success": False, "error": str(e), "author": None}


@mutation.field("getSession")
@auth_service.login_required
async def get_session(_: None, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    """Получает информацию о текущей сессии"""
    try:
        # Получаем токен из контекста (установлен декоратором login_required)
        token = info.context.get("token")
        author = info.context.get("author")

        if not token:
            return {"success": False, "token": None, "author": None, "error": "Токен не найден"}

        if not author:
            return {"success": False, "token": None, "author": None, "error": "Пользователь не найден"}

        return {"success": True, "token": token, "author": author, "error": None}
    except Exception as e:
        logger.error(f"Ошибка получения сессии: {e}")
        return {"success": False, "token": None, "author": None, "error": str(e)}


# === ЗАПРОСЫ ===


@query.field("isEmailUsed")
async def is_email_used(_: None, _info: GraphQLResolveInfo, email: str) -> bool:
    """Проверяет, используется ли email"""
    try:
        return auth_service.is_email_used(email)
    except Exception as e:
        logger.error(f"Ошибка проверки email: {e}")
        return False
