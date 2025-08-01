"""
Единый middleware для обработки авторизации в GraphQL запросах
"""

import json
import time
from collections.abc import Awaitable, MutableMapping
from typing import Any, Callable, Optional

from graphql import GraphQLResolveInfo
from sqlalchemy.orm import exc
from starlette.authentication import UnauthenticatedUser
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
            logger.debug("[auth.authenticate] Токен отсутствует")
            return AuthCredentials(
                author_id=None, scopes={}, logged_in=False, error_message="no token", email=None, token=None
            ), UnauthenticatedUser()

        # Проверяем сессию в Redis
        try:
            payload = await TokenManager.verify_session(token)
            if not payload:
                logger.debug("[auth.authenticate] Недействительный токен или сессия не найдена")
                return AuthCredentials(
                    author_id=None,
                    scopes={},
                    logged_in=False,
                    error_message="Invalid token or session",
                    email=None,
                    token=None,
                ), UnauthenticatedUser()

            with local_session() as session:
                try:
                    # payload может быть словарем или объектом, обрабатываем оба случая
                    user_id = payload.user_id if hasattr(payload, "user_id") else payload.get("user_id")
                    if not user_id:
                        logger.debug("[auth.authenticate] user_id не найден в payload")
                        return AuthCredentials(
                            author_id=None,
                            scopes={},
                            logged_in=False,
                            error_message="Invalid token payload",
                            email=None,
                            token=None,
                        ), UnauthenticatedUser()

                    author = session.query(Author).where(Author.id == user_id).one()

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

                    # Создаем пустой словарь разрешений
                    # Разрешения будут проверяться через RBAC систему по требованию
                    scopes: dict[str, Any] = {}

                    # Роли пользователя будут определяться в контексте конкретной операции
                    # через RBAC систему, а не здесь
                    roles = []

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
                    logger.debug("[auth.authenticate] Пользователь не найден в базе данных")
                    return AuthCredentials(
                        author_id=None,
                        scopes={},
                        logged_in=False,
                        error_message="User not found",
                        email=None,
                        token=None,
                    ), UnauthenticatedUser()
                except Exception as e:
                    logger.error(f"[auth.authenticate] Ошибка при работе с базой данных: {e}")
                    return AuthCredentials(
                        author_id=None, scopes={}, logged_in=False, error_message=str(e), email=None, token=None
                    ), UnauthenticatedUser()
        except Exception as e:
            logger.error(f"[auth.authenticate] Ошибка при проверке сессии: {e}")
            return AuthCredentials(
                author_id=None, scopes={}, logged_in=False, error_message=str(e), email=None, token=None
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

        # Извлекаем заголовки используя тот же механизм, что и get_safe_headers
        headers = {}

        # Первый приоритет: scope из ASGI (самый надежный источник)
        if "headers" in scope:
            scope_headers = scope.get("headers", [])
            if scope_headers:
                headers.update({k.decode("utf-8").lower(): v.decode("utf-8") for k, v in scope_headers})
                logger.debug(f"[middleware] Получены заголовки из scope: {len(headers)}")

                # Логируем все заголовки из scope для диагностики
                logger.debug(f"[middleware] Заголовки из scope: {list(headers.keys())}")

                # Логируем raw заголовки из scope
                logger.debug(f"[middleware] Raw scope headers: {scope_headers}")

                # Проверяем наличие authorization заголовка
                if "authorization" in headers:
                    logger.debug(f"[middleware] Authorization заголовок найден: {headers['authorization'][:50]}...")
                else:
                    logger.debug("[middleware] Authorization заголовок НЕ найден в scope headers")
        else:
            logger.debug("[middleware] Заголовки scope отсутствуют")

        # Логируем все заголовки для диагностики
        logger.debug(f"[middleware] Все заголовки: {list(headers.keys())}")

        # Логируем конкретные заголовки для диагностики
        auth_header_value = headers.get("authorization", "")
        logger.debug(f"[middleware] Authorization header: {auth_header_value[:50]}...")

        session_token_value = headers.get(SESSION_TOKEN_HEADER.lower(), "")
        logger.debug(f"[middleware] {SESSION_TOKEN_HEADER} header: {session_token_value[:50]}...")

        # Используем тот же механизм получения токена, что и в декораторе
        token = None

        # 0. Проверяем сохраненный токен в scope (приоритет)
        if "auth_token" in scope:
            token = scope["auth_token"]
            logger.debug(f"[middleware] Токен получен из scope.auth_token: {len(token)}")
        else:
            logger.debug("[middleware] scope.auth_token НЕ найден")

            # Стандартная система сессий уже обрабатывает кэширование
            # Дополнительной проверки Redis кэша не требуется

            # Отладка: детальная информация о запросе без Authorization
        if not token:
            method = scope.get("method", "UNKNOWN")
            path = scope.get("path", "UNKNOWN")
            logger.warning(f"[middleware] ЗАПРОС БЕЗ AUTHORIZATION: {method} {path}")
            logger.warning(f"[middleware] User-Agent: {headers.get('user-agent', 'НЕ НАЙДЕН')}")
            logger.warning(f"[middleware] Referer: {headers.get('referer', 'НЕ НАЙДЕН')}")
            logger.warning(f"[middleware] Origin: {headers.get('origin', 'НЕ НАЙДЕН')}")
            logger.warning(f"[middleware] Content-Type: {headers.get('content-type', 'НЕ НАЙДЕН')}")
            logger.warning(f"[middleware] Все заголовки: {list(headers.keys())}")

            # Проверяем, есть ли активные сессии в Redis
            try:
                from services.redis import redis as redis_adapter

                # Получаем все активные сессии
                session_keys = await redis_adapter.keys("session:*")
                logger.debug(f"[middleware] Найдено активных сессий в Redis: {len(session_keys)}")

                if session_keys:
                    # Пытаемся найти токен через активные сессии
                    for session_key in session_keys[:3]:  # Проверяем первые 3 сессии
                        try:
                            session_data = await redis_adapter.hgetall(session_key)
                            if session_data:
                                logger.debug(f"[middleware] Найдена активная сессия: {session_key}")
                                # Извлекаем user_id из ключа сессии
                                user_id = (
                                    session_key.decode("utf-8").split(":")[1]
                                    if isinstance(session_key, bytes)
                                    else session_key.split(":")[1]
                                )
                                logger.debug(f"[middleware] User ID из сессии: {user_id}")
                                break
                        except Exception as e:
                            logger.debug(f"[middleware] Ошибка чтения сессии {session_key}: {e}")
                else:
                    logger.debug("[middleware] Активных сессий в Redis не найдено")

            except Exception as e:
                logger.debug(f"[middleware] Ошибка проверки сессий: {e}")

        # 1. Проверяем заголовок Authorization
        if not token:
            auth_header = headers.get("authorization", "")
            if auth_header:
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:].strip()
                    logger.debug(f"[middleware] Токен получен из заголовка Authorization: {len(token)}")
                else:
                    token = auth_header.strip()
                    logger.debug(f"[middleware] Прямой токен получен из заголовка Authorization: {len(token)}")

        # 2. Проверяем основной заголовок авторизации, если Authorization не найден
        if not token:
            auth_header = headers.get(SESSION_TOKEN_HEADER.lower(), "")
            if auth_header:
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:].strip()
                    logger.debug(f"[middleware] Токен получен из заголовка {SESSION_TOKEN_HEADER}: {len(token)}")
                else:
                    token = auth_header.strip()
                    logger.debug(f"[middleware] Прямой токен получен из заголовка {SESSION_TOKEN_HEADER}: {len(token)}")

        # 3. Проверяем cookie
        if not token:
            cookies = headers.get("cookie", "")
            logger.debug(f"[middleware] Проверяем cookies: {cookies[:100]}...")
            cookie_items = cookies.split(";")
            for item in cookie_items:
                if "=" in item:
                    name, value = item.split("=", 1)
                    if name.strip() == SESSION_COOKIE_NAME:
                        token = value.strip()
                        logger.debug(f"[middleware] Токен получен из cookie {SESSION_COOKIE_NAME}: {len(token)}")
                        break

        if token:
            logger.debug(f"[middleware] Токен найден: {len(token)} символов")
        else:
            logger.debug("[middleware] Токен не найден")

        # Аутентифицируем пользователя
        auth, user = await self.authenticate_user(token or "")

        # Добавляем в scope данные авторизации и пользователя
        scope["auth"] = auth
        scope["user"] = user

        # Сохраняем токен в scope для использования в последующих запросах
        if token:
            scope["auth_token"] = token
            logger.debug(f"[middleware] Токен сохранен в scope.auth_token: {len(token)}")
            logger.debug(f"[middleware] Пользователь аутентифицирован: {user.is_authenticated}")

            # Токен уже сохранен в стандартной системе сессий через SessionTokenManager
            # Дополнительного кэширования не требуется
            logger.debug("[middleware] Токен обработан стандартной системой сессий")
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
