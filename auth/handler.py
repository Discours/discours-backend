from ariadne.asgi.handlers import GraphQLHTTPHandler
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
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
        # Получаем стандартный контекст от базового класса
        context = await super().get_context_for_request(request, data)
        
        # Создаем объект ответа для установки cookie
        response = JSONResponse({})
        context["response"] = response
        
        # Интегрируем с AuthMiddleware
        auth_middleware.set_context(context)
        context["extensions"] = auth_middleware
        
        # Добавляем данные авторизации только если они доступны
        # Без проверки hasattr, так как это вызывает ошибку до обработки AuthenticationMiddleware
        if hasattr(request, "auth") and request.auth:
            # Используем request.auth вместо request.user, так как user еще не доступен
            context["auth"] = request.auth
            # Безопасно логируем информацию о типе объекта auth
            logger.debug(f"[graphql] Добавлены данные авторизации в контекст: {type(request.auth).__name__}")
            
        logger.debug(f"[graphql] Подготовлен расширенный контекст для запроса")
        
        return context
