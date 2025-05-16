"""
Middleware для обработки авторизации в GraphQL запросах
"""

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Scope, Receive, Send
from utils.logger import root_logger as logger
from settings import SESSION_TOKEN_HEADER, SESSION_COOKIE_NAME


class AuthorizationMiddleware:
    """
    Middleware для обработки заголовка Authorization и cookie авторизации.
    Извлекает Bearer токен из заголовка или cookie и добавляет его в заголовки
    запроса для обработки стандартным AuthenticationMiddleware Starlette.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Извлекаем заголовки
        headers = Headers(scope=scope)
        auth_header = headers.get(SESSION_TOKEN_HEADER)
        token = None

        # Сначала пробуем получить токен из заголовка Authorization
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "", 1).strip()
                logger.debug(
                    f"[middleware] Извлечен Bearer токен из заголовка, длина: {len(token) if token else 0}"
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
                            f"[middleware] Извлечен токен из cookie, длина: {len(token) if token else 0}"
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
            if "auth" not in scope:
                scope["auth"] = {"type": "bearer", "token": token}

        await self.app(scope, receive, send)


class GraphQLExtensionsMiddleware:
    """
    Утилиты для расширения контекста GraphQL запросов
    """

    def set_cookie(self, key, value, **options):
        """Устанавливает cookie в ответе"""
        context = getattr(self, "_context", None)
        if context and "response" in context and hasattr(context["response"], "set_cookie"):
            context["response"].set_cookie(key, value, **options)

    def delete_cookie(self, key, **options):
        """Удаляет cookie из ответа"""
        context = getattr(self, "_context", None)
        if context and "response" in context and hasattr(context["response"], "delete_cookie"):
            context["response"].delete_cookie(key, **options)

    async def resolve(self, next, root, info, *args, **kwargs):
        """
        Middleware для обработки запросов GraphQL.
        Добавляет методы для установки cookie в контекст.
        """
        try:
            # Получаем доступ к контексту запроса
            context = info.context

            # Сохраняем ссылку на контекст
            self._context = context

            # Добавляем себя как объект, содержащий утилитные методы
            context["extensions"] = self

            return await next(root, info, *args, **kwargs)
        except Exception as e:
            logger.error(f"[GraphQLExtensionsMiddleware] Ошибка: {str(e)}")
            raise
