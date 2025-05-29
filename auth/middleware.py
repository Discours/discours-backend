"""
Middleware для обработки авторизации в GraphQL запросах
"""

from typing import Any, Dict

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from settings import (
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_TOKEN_HEADER,
)
from utils.logger import root_logger as logger


class AuthMiddleware:
    """
    Универсальный middleware для обработки авторизации и управления cookies.

    Основные функции:
    1. Извлечение Bearer токена из заголовка Authorization или cookie
    2. Добавление токена в заголовки запроса для обработки AuthenticationMiddleware
    3. Предоставление методов для установки/удаления cookies в GraphQL резолверах
    """

    def __init__(self, app: ASGIApp):
        self.app = app
        self._context = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Обработка ASGI запроса"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Извлекаем заголовки
        headers = Headers(scope=scope)
        token = None
        token_source = None

        # Сначала пробуем получить токен из заголовка авторизации
        auth_header = headers.get(SESSION_TOKEN_HEADER)
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "", 1).strip()
                token_source = "header"
                logger.debug(
                    f"[middleware] Извлечен Bearer токен из заголовка {SESSION_TOKEN_HEADER}, длина: {len(token) if token else 0}"
                )
            else:
                # Если заголовок не начинается с Bearer, предполагаем, что это чистый токен
                token = auth_header.strip()
                token_source = "header"
                logger.debug(
                    f"[middleware] Извлечен прямой токен из заголовка {SESSION_TOKEN_HEADER}, длина: {len(token) if token else 0}"
                )

        # Если токен не получен из основного заголовка и это не Authorization, проверяем заголовок Authorization
        if not token and SESSION_TOKEN_HEADER.lower() != "authorization":
            auth_header = headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "", 1).strip()
                token_source = "auth_header"
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
                        token_source = "cookie"
                        logger.debug(
                            f"[middleware] Извлечен токен из cookie {SESSION_COOKIE_NAME}, длина: {len(token) if token else 0}"
                        )
                        break

        # Если токен получен, обновляем заголовки в scope
        if token:
            # Создаем новый список заголовков
            new_headers = []
            for name, value in scope["headers"]:
                # Пропускаем оригинальный заголовок авторизации
                if name.decode("latin1").lower() != SESSION_TOKEN_HEADER.lower():
                    new_headers.append((name, value))

            # Добавляем заголовок с чистым токеном
            new_headers.append((SESSION_TOKEN_HEADER.encode("latin1"), token.encode("latin1")))

            # Обновляем заголовки в scope
            scope["headers"] = new_headers

            # Также добавляем информацию о типе аутентификации для дальнейшего использования
            scope["auth"] = {"type": "bearer", "token": token, "source": token_source}
            logger.debug(f"[middleware] Токен добавлен в scope для аутентификации из источника: {token_source}")
        else:
            logger.debug(f"[middleware] Токен не найден ни в заголовке, ни в cookie")

        await self.app(scope, receive, send)

    def set_context(self, context):
        """Сохраняет ссылку на контекст GraphQL запроса"""
        self._context = context
        logger.debug(f"[middleware] Установлен контекст GraphQL: {bool(context)}")

    def set_cookie(self, key, value, **options):
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
                logger.error(f"[middleware] Ошибка при установке cookie {key} через response: {str(e)}")

        # Способ 2: Через собственный response в контексте
        if not success and hasattr(self, "_response") and self._response and hasattr(self._response, "set_cookie"):
            try:
                self._response.set_cookie(key, value, **options)
                logger.debug(f"[middleware] Установлена cookie {key} через _response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при установке cookie {key} через _response: {str(e)}")

        if not success:
            logger.error(f"[middleware] Не удалось установить cookie {key}: объекты response недоступны")

    def delete_cookie(self, key, **options):
        """
        Удаляет cookie из ответа

        Args:
            key: Имя cookie для удаления
            **options: Дополнительные параметры
        """
        success = False

        # Способ 1: Через response
        if self._context and "response" in self._context and hasattr(self._context["response"], "delete_cookie"):
            try:
                self._context["response"].delete_cookie(key, **options)
                logger.debug(f"[middleware] Удалена cookie {key} через response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при удалении cookie {key} через response: {str(e)}")

        # Способ 2: Через собственный response в контексте
        if not success and hasattr(self, "_response") and self._response and hasattr(self._response, "delete_cookie"):
            try:
                self._response.delete_cookie(key, **options)
                logger.debug(f"[middleware] Удалена cookie {key} через _response")
                success = True
            except Exception as e:
                logger.error(f"[middleware] Ошибка при удалении cookie {key} через _response: {str(e)}")

        if not success:
            logger.error(f"[middleware] Не удалось удалить cookie {key}: объекты response недоступны")

    async def resolve(self, next, root, info, *args, **kwargs):
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

            logger.debug(
                f"[middleware] GraphQL resolve: контекст подготовлен, добавлены расширения для работы с cookie"
            )

            return await next(root, info, *args, **kwargs)
        except Exception as e:
            logger.error(f"[AuthMiddleware] Ошибка в GraphQL resolve: {str(e)}")
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

                    result_data = json.loads(result.body.decode("utf-8"))
                except Exception as e:
                    logger.error(f"[process_result] Не удалось извлечь данные из JSONResponse: {str(e)}")
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
                logger.error(f"[process_result] Ошибка при обработке POST запроса: {str(e)}")

        return response


# Создаем единый экземпляр AuthMiddleware для использования с GraphQL
auth_middleware = AuthMiddleware(lambda scope, receive, send: None)
