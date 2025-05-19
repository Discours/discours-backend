"""
Middleware для обработки авторизации в GraphQL запросах
"""

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Scope, Receive, Send
from utils.logger import root_logger as logger
from settings import SESSION_TOKEN_HEADER, SESSION_COOKIE_NAME


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
    
    def set_context(self, context):
        """Сохраняет ссылку на контекст GraphQL запроса"""
        self._context = context
    
    def set_cookie(self, key, value, **options):
        """Устанавливает cookie в ответе"""
        if self._context and "response" in self._context and hasattr(self._context["response"], "set_cookie"):
            self._context["response"].set_cookie(key, value, **options)

    def delete_cookie(self, key, **options):
        """Удаляет cookie из ответа"""
        if self._context and "response" in self._context and hasattr(self._context["response"], "delete_cookie"):
            self._context["response"].delete_cookie(key, **options)

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
            
            return await next(root, info, *args, **kwargs)
        except Exception as e:
            logger.error(f"[AuthMiddleware] Ошибка в GraphQL resolve: {str(e)}")
            raise
