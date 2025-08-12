from typing import Any

from ariadne.asgi.handlers import GraphQLHTTPHandler
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth.middleware import auth_middleware
from utils.logger import root_logger as logger


class EnhancedGraphQLHTTPHandler(GraphQLHTTPHandler):
    """
    Улучшенный GraphQL HTTP обработчик с поддержкой cookie и авторизации.

    Расширяет стандартный GraphQLHTTPHandler для:
    1. Создания расширенного контекста запроса с авторизационными данными
    2. Корректной обработки ответов с cookie и headers
    3. Интеграции с AuthMiddleware
    """

    async def get_context_for_request(self, request: Request, data: dict) -> dict:
        """
        Расширяем контекст для GraphQL запросов.

        Добавляет к стандартному контексту:
        - Объект response для установки cookie
        - Интеграцию с AuthMiddleware
        - Расширения для управления авторизацией

        Args:
            request: Starlette Request объект
            data: данные запроса

        Returns:
            dict: контекст с дополнительными данными для авторизации и cookie
        """
        # Безопасно получаем заголовки для диагностики
        headers = {}
        if hasattr(request, "headers"):
            try:
                # Используем безопасный способ получения заголовков
                for key, value in request.headers.items():
                    headers[key.lower()] = value
            except Exception as e:
                logger.debug(f"[graphql] Ошибка при получении заголовков: {e}")

        logger.debug(f"[graphql] Заголовки в get_context_for_request: {list(headers.keys())}")
        if "authorization" in headers:
            logger.debug(f"[graphql] Authorization header найден: {headers['authorization'][:50]}...")
        else:
            logger.debug("[graphql] Authorization header НЕ найден")

        # Получаем стандартный контекст от базового класса
        context = await super().get_context_for_request(request, data)

        # Создаем объект ответа для установки cookie
        response = JSONResponse({})
        context["response"] = response

        # Интегрируем с AuthMiddleware
        auth_middleware.set_context(context)
        context["extensions"] = auth_middleware

        # Добавляем данные авторизации только если они доступны
        # Проверяем наличие данных авторизации в scope
        if hasattr(request, "scope") and isinstance(request.scope, dict) and "auth" in request.scope:
            auth_cred: Any | None = request.scope.get("auth")
            context["auth"] = auth_cred
            # Безопасно логируем информацию о типе объекта auth
            logger.debug(f"[graphql] Добавлены данные авторизации в контекст из scope: {type(auth_cred).__name__}")

            # Проверяем, есть ли токен в auth_cred
            if auth_cred is not None and hasattr(auth_cred, "token") and getattr(auth_cred, "token"):
                token_val = auth_cred.token
                token_len = len(token_val) if hasattr(token_val, "__len__") else 0
                logger.debug(f"[graphql] Токен найден в auth_cred: {token_len}")
            else:
                logger.debug("[graphql] Токен НЕ найден в auth_cred")

            # Добавляем author_id в контекст для RBAC
            author_id = None
            if auth_cred is not None and hasattr(auth_cred, "author_id") and getattr(auth_cred, "author_id"):
                author_id = auth_cred.author_id
            elif isinstance(auth_cred, dict) and "author_id" in auth_cred:
                author_id = auth_cred["author_id"]

            if author_id:
                # Преобразуем author_id в число для совместимости с RBAC
                try:
                    author_id_int = int(str(author_id).strip())
                    context["author"] = {"id": author_id_int}
                    logger.debug(f"[graphql] Добавлен author_id в контекст: {author_id_int}")
                except (ValueError, TypeError) as e:
                    logger.error(f"[graphql] Ошибка преобразования author_id {author_id}: {e}")
                    context["author"] = {"id": author_id}
                    logger.debug(f"[graphql] Добавлен author_id как строка: {author_id}")
            else:
                logger.debug("[graphql] author_id не найден в auth_cred")
        else:
            logger.debug("[graphql] Данные авторизации НЕ найдены в scope")

        logger.debug("[graphql] Подготовлен расширенный контекст для запроса")

        return context
