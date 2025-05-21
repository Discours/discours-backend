import asyncio
import os
from importlib import import_module
from os.path import exists, join

from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLHTTPHandler
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp

from cache.precache import precache_data
from cache.revalidator import revalidation_manager
from services.exception import ExceptionHandlerMiddleware
from services.redis import redis
from services.schema import create_all_tables, resolvers
from services.search import search_service, initialize_search_index

from utils.logger import root_logger as logger
from auth.internal import InternalAuthentication
from auth.middleware import AuthMiddleware 
from settings import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_MAX_AGE,
    SESSION_TOKEN_HEADER,
)

# Импортируем резолверы
import_module("resolvers")

# Создаем схему GraphQL
schema = make_executable_schema(load_schema_from_path("schema/"), resolvers)

# Пути к клиентским файлам
DIST_DIR = join(os.path.dirname(__file__), "dist")  # Директория для собранных файлов
INDEX_HTML = join(os.path.dirname(__file__), "index.html")


async def check_search_service():
    """Check if search service is available and log result"""
    info = await search_service.info()
    if info.get("status") in ["error", "unavailable"]:
        print(f"[WARNING] Search service unavailable: {info.get('message', 'unknown reason')}")
    else:
        print(f"[INFO] Search service is available: {info}")
        

async def index_handler(request: Request):
    """
    Раздача основного HTML файла
    """
    return FileResponse(INDEX_HTML)


# Создаем единый экземпляр AuthMiddleware для использования с GraphQL
auth_middleware = AuthMiddleware(lambda scope, receive, send: None)


class EnhancedGraphQLHTTPHandler(GraphQLHTTPHandler):
    """
    Улучшенный GraphQL HTTP обработчик с поддержкой cookie и авторизации
    """
    
    async def get_context_for_request(self, request: Request, data: dict) -> dict:
        """
        Расширяем контекст для GraphQL запросов
        """
        # Получаем стандартный контекст от базового класса
        context = await super().get_context_for_request(request, data)
        
        # Создаем объект ответа для установки cookie
        response = JSONResponse({})
        context["response"] = response
        
        # Интегрируем с AuthMiddleware
        auth_middleware.set_context(context)
        context["extensions"] = auth_middleware
        
        logger.debug(f"[graphql] Подготовлен расширенный контекст для запроса")
        
        return context
    
    async def process_result(self, request: Request, result: dict) -> Response:
        """
        Обрабатывает результат GraphQL запроса, поддерживая установку cookie
        """
        # Получаем контекст запроса
        context = getattr(request, "context", {})
        
        # Получаем заранее созданный response из контекста
        response = context.get("response") 
        
        if not response or not isinstance(response, Response):
            # Если response не найден или не является объектом Response, создаем новый
            response = await super().process_result(request, result)
        else:
            # Обновляем тело ответа данными из результата GraphQL
            response.body = self.encode_json(result)
            response.headers["content-type"] = "application/json"
            response.headers["content-length"] = str(len(response.body))
        
        logger.debug(f"[graphql] Подготовлен ответ с типом {type(response).__name__}")
        
        return response


# Функция запуска сервера
async def start():
    """Запуск сервера и инициализация данных"""
    # Инициализируем соединение с Redis
    await redis.connect()
    logger.info("Установлено соединение с Redis")

    # Создаем все таблицы в БД
    create_all_tables()

    # Запускаем предварительное кеширование данных
    asyncio.create_task(precache_data())

    # Запускаем задачу ревалидации кеша
    asyncio.create_task(revalidation_manager.start())

    # Выводим сообщение о запуске сервера и доступности API
    logger.info("Сервер запущен и готов принимать запросы")
    logger.info("GraphQL API доступно по адресу: /graphql")
    logger.info("Админ-панель доступна по адресу: http://127.0.0.1:8000/")


# Функция остановки сервера
async def shutdown():
    """Остановка сервера и освобождение ресурсов"""
    logger.info("Остановка сервера")

    # Закрываем соединение с Redis
    await redis.disconnect()

    # Останавливаем поисковый сервис
    search_service.close()

    # Удаляем PID-файл, если он существует
    from settings import DEV_SERVER_PID_FILE_NAME
    if exists(DEV_SERVER_PID_FILE_NAME):
        os.unlink(DEV_SERVER_PID_FILE_NAME)


# Создаем middleware с правильным порядком
middleware = [
    # Начинаем с обработки ошибок
    Middleware(ExceptionHandlerMiddleware),
    # CORS должен быть перед другими middleware для корректной обработки preflight-запросов
    Middleware(
        CORSMiddleware,
        allow_origins=[
            "https://localhost:3000", 
            "https://testing.discours.io", 
            "https://discours.io", 
            "https://new.discours.io",
            "https://discours.ru",
            "https://new.discours.ru"
            ],
        allow_methods=["GET", "POST", "OPTIONS"],  # Явно указываем OPTIONS 
        allow_headers=["*"],
        allow_credentials=True,
    ),
    # После CORS идёт обработка авторизации
    Middleware(AuthMiddleware),
    # И затем аутентификация
    Middleware(AuthenticationMiddleware, backend=InternalAuthentication()),
]


# Создаем экземпляр GraphQL с улучшенным обработчиком
graphql_app = GraphQL(
    schema, 
    debug=True,
    http_handler=EnhancedGraphQLHTTPHandler()
)


# Оборачиваем GraphQL-обработчик для лучшей обработки ошибок
async def graphql_handler(request: Request):
    if request.method not in ["GET", "POST", "OPTIONS"]:
        return JSONResponse({"error": "Method Not Allowed by main.py"}, status_code=405)

    try:
        # Обрабатываем CORS для OPTIONS запросов
        if request.method == "OPTIONS":
            response = JSONResponse({})
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
            return response
        
        result = await graphql_app.handle_request(request)
        
        # Если результат не является Response, преобразуем его в JSONResponse
        if not isinstance(result, Response):
            response = JSONResponse(result)
            
            # Проверяем, был ли токен в запросе или ответе
            if request.method == "POST" and isinstance(result, dict):
                data = await request.json()
                op_name = data.get("operationName", "").lower()
                
                # Если это операция логина или обновления токена, и в ответе есть токен
                if (op_name in ["login", "refreshtoken"]) and result.get("data", {}).get(op_name, {}).get("token"):
                    token = result["data"][op_name]["token"]
                    # Устанавливаем cookie с токеном
                    response.set_cookie(
                        key=SESSION_COOKIE_NAME,
                        value=token,
                        httponly=SESSION_COOKIE_HTTPONLY,
                        secure=SESSION_COOKIE_SECURE,
                        samesite=SESSION_COOKIE_SAMESITE,
                        max_age=SESSION_COOKIE_MAX_AGE,
                    )
                    logger.debug(f"[graphql_handler] Установлена cookie {SESSION_COOKIE_NAME} для операции {op_name}")
                
                # Если это операция logout, удаляем cookie
                elif op_name == "logout":
                    response.delete_cookie(
                        key=SESSION_COOKIE_NAME,
                        secure=SESSION_COOKIE_SECURE,
                        httponly=SESSION_COOKIE_HTTPONLY,
                        samesite=SESSION_COOKIE_SAMESITE
                    )
                    logger.debug(f"[graphql_handler] Удалена cookie {SESSION_COOKIE_NAME} для операции {op_name}")
            
            return response
        
        return result
    except asyncio.CancelledError:
        return JSONResponse({"error": "Request cancelled"}, status_code=499)
    except Exception as e:
        logger.error(f"GraphQL error: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)
    
# Добавляем маршруты, порядок имеет значение
routes = [
    Route("/graphql", graphql_handler, methods=["GET", "POST", "OPTIONS"]),
    Mount("/", app=StaticFiles(directory=DIST_DIR, html=True)),
]

# Создаем приложение Starlette с маршрутами и middleware
app = Starlette(
    routes=routes,
    middleware=middleware,
    on_startup=[start],
    on_shutdown=[shutdown],
)
