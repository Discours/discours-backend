"""
Единый middleware для обработки авторизации в GraphQL запросах
"""

import time
from collections.abc import Awaitable, MutableMapping
from typing import Any, Callable, Optional

from graphql import GraphQLResolveInfo
from sqlalchemy.orm import exc
from starlette.authentication import UnauthenticatedUser
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from auth.credentials import AuthCredentials
from auth.orm import Author
from auth.tokens.storage import TokenStorage as TokenManager
from services.db import local_session
from settings import (
    ADMIN_EMAILS as ADMIN_EMAILS_LIST,
)
from settings import (
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_TOKEN_HEADER,
)
from utils.logger import root_logger as logger

ADMIN_EMAILS = ADMIN_EMAILS_LIST.split(",")


class AuthenticatedUser:
    """Аутентифицированный пользователь"""

    def __init__(
        self,
        user_id: str,
        username: str = "",
        roles: Optional[list] = None,
        permissions: Optional[dict] = None,
        token: Optional[str] = None,
    ) -> None:
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


class AuthMiddleware:
    """
    Единый middleware для обработки авторизации и аутентификации.

    Основные функции:
    1. Извлечение Bearer токена из заголовка Authorization или cookie
    2. Проверка сессии через TokenStorage
    3. Создание request.user и request.auth
    4. Предоставление методов для установки/удаления cookies
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._context = None

    async def authenticate_user(self, token: str) -> tuple[AuthCredentials, AuthenticatedUser | UnauthenticatedUser]:
        """Аутентифицирует пользователя по токену"""
        if not token:
            return AuthCredentials(
                author_id=None, scopes={}, logged_in=False, error_message="no token", email=None, token=None
            ), UnauthenticatedUser()

        # Проверяем сессию в Redis
        payload = await TokenManager.verify_session(token)
        if not payload:
            logger.debug("[auth.authenticate] Недействительный токен")
            return AuthCredentials(
                author_id=None, scopes={}, logged_in=False, error_message="Invalid token", email=None, token=None
            ), UnauthenticatedUser()

        with local_session() as session:
            try:
                author = session.query(Author).filter(Author.id == payload.user_id).one()

                if author.is_locked():
                    logger.debug(f"[auth.authenticate] Аккаунт заблокирован: {author.id}")
                    return AuthCredentials(
                        author_id=None,
                        scopes={},
                        logged_in=False,
                        error_message="Account is locked",
                        email=None,
                        token=None,
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
                    error_message="",
                    email=author.email,
                    token=token,
                )

                user = AuthenticatedUser(
                    user_id=str(author.id),
                    username=author.slug or author.email or "",
                    roles=roles,
                    permissions=scopes,
                    token=token,
                )

                logger.debug(f"[auth.authenticate] Успешная аутентификация: {author.email}")
                return credentials, user

            except exc.NoResultFound:
                logger.debug("[auth.authenticate] Пользователь не найден")
                return AuthCredentials(
                    author_id=None, scopes={}, logged_in=False, error_message="User not found", email=None, token=None
                ), UnauthenticatedUser()

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        """Обработка ASGI запроса"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Извлекаем заголовки
        headers = Headers(scope=scope)
        token = None

        # Сначала пробуем получить токен из заголовка авторизации
        auth_header = headers.get(SESSION_TOKEN_HEADER)
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "", 1).strip()
                logger.debug(
                    f"[middleware] Извлечен Bearer токен из заголовка {SESSION_TOKEN_HEADER}, длина: {len(token) if token else 0}"
                )
            else:
                # Если заголовок не начинается с Bearer, предполагаем, что это чистый токен
                token = auth_header.strip()
                logger.debug(
                    f"[middleware] Извлечен прямой токен из заголовка {SESSION_TOKEN_HEADER}, длина: {len(token) if token else 0}"
                )

        # Если токен не получен из основного заголовка и это не Authorization, проверяем заголовок Authorization
        if not token and SESSION_TOKEN_HEADER.lower() != "authorization":
            auth_header = headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "", 1).strip()
                logger.debug(
                    f"[middleware] Извлечен Bearer токен из заголовка Authorization, длина: {len(token) if token else 0}"
                )

        # Если токен не получен из заголовка, пробуем взять из cookie
        if not token:
            cookies = headers.get("cookie", "")
            cookie_items = cookies.split(";")
            for item in cookie_items:
                if "=" in item:
                    name, value = item.split("=", 1)
                    if name.strip() == SESSION_COOKIE_NAME:
                        token = value.strip()
                        logger.debug(
                            f"[middleware] Извлечен токен из cookie {SESSION_COOKIE_NAME}, длина: {len(token) if token else 0}"
                        )
                        break

        # Аутентифицируем пользователя
        auth, user = await self.authenticate_user(token or "")

        # Добавляем в scope данные авторизации и пользователя
        scope["auth"] = auth
        scope["user"] = user

        if token:
            # Обновляем заголовки в scope для совместимости
            new_headers: list[tuple[bytes, bytes]] = []
            for name, value in scope["headers"]:
                header_name = name.decode("latin1") if isinstance(name, bytes) else str(name)
                if header_name.lower() != SESSION_TOKEN_HEADER.lower():
                    # Ensure both name and value are bytes
                    name_bytes = name if isinstance(name, bytes) else str(name).encode("latin1")
                    value_bytes = value if isinstance(value, bytes) else str(value).encode("latin1")
                    new_headers.append((name_bytes, value_bytes))
            new_headers.append((SESSION_TOKEN_HEADER.encode("latin1"), token.encode("latin1")))
            scope["headers"] = new_headers

            logger.debug(f"[middleware] Пользователь аутентифицирован: {user.is_authenticated}")
        else:
            logger.debug("[middleware] Токен не найден, пользователь неаутентифицирован")

        await self.app(scope, receive, send)

    def set_context(self, context) -> None:
        """Сохраняет ссылку на контекст GraphQL запроса"""
        self._context = context
        logger.debug(f"[middleware] Установлен контекст GraphQL: {bool(context)}")

    def set_cookie(self, key: str, value: str, **options: Any) -> None:
        """
        Устанавливает cookie в ответе

        Args:
            key: Имя cookie
            value: Значение cookie
            **options: Дополнительные параметры (httponly, secure, max_age, etc.)
        """
        success = False

        # Способ 1: Через response
        if self._context and "response" in self._context and hasattr(self._context["response"], "set_cookie"):
            try:
                self._context["response"].set_cookie(key, value, **options)
                logger.debug(f"[middleware] Установлена cookie {key} через response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при установке cookie {key} через response: {e!s}")

        # Способ 2: Через собственный response в контексте
        if not success and hasattr(self, "_response") and self._response and hasattr(self._response, "set_cookie"):
            try:
                self._response.set_cookie(key, value, **options)
                logger.debug(f"[middleware] Установлена cookie {key} через _response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при установке cookie {key} через _response: {e!s}")

        if not success:
            logger.error(f"[middleware] Не удалось установить cookie {key}: объекты response недоступны")

    def delete_cookie(self, key: str, **options: Any) -> None:
        """
        Удаляет cookie из ответа
        """
        success = False

        # Способ 1: Через response
        if self._context and "response" in self._context and hasattr(self._context["response"], "delete_cookie"):
            try:
                self._context["response"].delete_cookie(key, **options)
                logger.debug(f"[middleware] Удалена cookie {key} через response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при удалении cookie {key} через response: {e!s}")

        # Способ 2: Через собственный response в контексте
        if not success and hasattr(self, "_response") and self._response and hasattr(self._response, "delete_cookie"):
            try:
                self._response.delete_cookie(key, **options)
                logger.debug(f"[middleware] Удалена cookie {key} через _response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при удалении cookie {key} через _response: {e!s}")

        if not success:
            logger.error(f"[middleware] Не удалось удалить cookie {key}: объекты response недоступны")

    async def resolve(
        self, next_resolver: Callable[..., Any], root: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any
    ) -> Any:
        """
        Middleware для обработки запросов GraphQL.
        Добавляет методы для установки cookie в контекст.
        """
        try:
            # Получаем доступ к контексту запроса
            context = info.context

            # Сохраняем ссылку на контекст
            self.set_context(context)

            # Добавляем себя как объект, содержащий утилитные методы
            context["extensions"] = self

            # Проверяем наличие response в контексте
            if "response" not in context or not context["response"]:
                from starlette.responses import JSONResponse

                context["response"] = JSONResponse({})
                logger.debug("[middleware] Создан новый response объект в контексте GraphQL")

            logger.debug("[middleware] GraphQL resolve: контекст подготовлен, добавлены расширения для работы с cookie")

            return await next_resolver(root, info, *args, **kwargs)
        except Exception as e:
            logger.error(f"[AuthMiddleware] Ошибка в GraphQL resolve: {e!s}")
            raise

    async def process_result(self, request: Request, result: Any) -> Response:
        """
        Обрабатывает результат GraphQL запроса, поддерживая установку cookie

        Args:
            request: Starlette Request объект
            result: результат GraphQL запроса (dict или Response)

        Returns:
            Response: HTTP-ответ с результатом и cookie (если необходимо)
        """

        # Проверяем, является ли result уже объектом Response
        if isinstance(result, Response):
            response = result
            # Пытаемся получить данные из response для проверки логина/логаута
            result_data = {}
            if isinstance(result, JSONResponse):
                try:
                    import json

                    body_content = result.body
                    if isinstance(body_content, (bytes, memoryview)):
                        body_text = bytes(body_content).decode("utf-8")
                        result_data = json.loads(body_text)
                    else:
                        result_data = json.loads(str(body_content))
                except Exception as e:
                    logger.error(f"[process_result] Не удалось извлечь данные из JSONResponse: {e!s}")
        else:
            response = JSONResponse(result)
            result_data = result

        # Проверяем, был ли токен в запросе или ответе
        if request.method == "POST":
            try:
                data = await request.json()
                op_name = data.get("operationName", "").lower()

                # Если это операция логина или обновления токена, и в ответе есть токен
                if op_name in ["login", "refreshtoken"]:
                    token = None
                    # Пытаемся извлечь токен из данных ответа
                    if result_data and isinstance(result_data, dict):
                        data_obj = result_data.get("data", {})
                        if isinstance(data_obj, dict) and op_name in data_obj:
                            op_result = data_obj.get(op_name, {})
                            if isinstance(op_result, dict) and "token" in op_result:
                                token = op_result.get("token")

                    if token:
                        # Устанавливаем cookie с токеном
                        response.set_cookie(
                            key=SESSION_COOKIE_NAME,
                            value=token,
                            httponly=SESSION_COOKIE_HTTPONLY,
                            secure=SESSION_COOKIE_SECURE,
                            samesite=SESSION_COOKIE_SAMESITE,
                            max_age=SESSION_COOKIE_MAX_AGE,
                        )
                        logger.debug(
                            f"[graphql_handler] Установлена cookie {SESSION_COOKIE_NAME} для операции {op_name}"
                        )

                # Если это операция logout, удаляем cookie
                elif op_name == "logout":
                    response.delete_cookie(
                        key=SESSION_COOKIE_NAME,
                        secure=SESSION_COOKIE_SECURE,
                        httponly=SESSION_COOKIE_HTTPONLY,
                        samesite=SESSION_COOKIE_SAMESITE,
                    )
                    logger.debug(f"[graphql_handler] Удалена cookie {SESSION_COOKIE_NAME} для операции {op_name}")
            except Exception as e:
                logger.error(f"[process_result] Ошибка при обработке POST запроса: {e!s}")

        return response


# Создаем единый экземпляр AuthMiddleware для использования с GraphQL
async def _dummy_app(
    scope: MutableMapping[str, Any],
    receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
    send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
) -> None:
    """Dummy ASGI app for middleware initialization"""


auth_middleware = AuthMiddleware(_dummy_app)
