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
from services.search import search_service

from utils.logger import root_logger as logger
from auth.internal import InternalAuthentication
from auth.middleware import AuthMiddleware 

# Импортируем резолверы
import_module("resolvers")

# Создаем схему GraphQL
schema = make_executable_schema(load_schema_from_path("schema/"), resolvers)

# Пути к клиентским файлам
DIST_DIR = join(os.path.dirname(__file__), "dist")  # Директория для собранных файлов
INDEX_HTML = join(os.path.dirname(__file__), "index.html")


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
        
        # Добавляем объект ответа для установки cookie
        response = JSONResponse({})
        context["response"] = response
        
        # Интегрируем с AuthMiddleware
        context["extensions"] = auth_middleware
        
        return context


# Функция запуска сервера
async def start():
    """Запуск сервера и инициализация данных"""
    # Создаем все таблицы в БД
    create_all_tables()

    # Запускаем предварительное кеширование данных
    asyncio.create_task(precache_data())

    # Запускаем задачу ревалидации кеша
    asyncio.create_task(revalidation_manager.start())

    # Выводим сообщение о запуске сервера и доступности API
    logger.info("Сервер запущен и готов принимать запросы")
    logger.info("GraphQL API доступно по адресу: /graphql")
    logger.info("Админ-панель доступна по адресу: /admin")


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
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],  # Явно указываем OPTIONS 
        allow_headers=["*"],
        allow_credentials=True,
    ),
    # После CORS идёт обработка авторизации
    Middleware(AuthMiddleware),
    # И затем аутентификация
    Middleware(AuthenticationMiddleware, backend=InternalAuthentication()),
]


# Создаем экземпляр GraphQL
graphql_app = GraphQL(schema, debug=True)


# Оборачиваем GraphQL-обработчик для лучшей обработки ошибок
async def graphql_handler(request: Request):
    if request.method not in ["GET", "POST", "OPTIONS"]:
        return JSONResponse({"error": "Method Not Allowed by main.py"}, status_code=405)

    try:
        result = await graphql_app.handle_request(request)
        if isinstance(result, Response):
            return result
        return JSONResponse(result)
    except asyncio.CancelledError:
        return JSONResponse({"error": "Request cancelled"}, status_code=499)
    except Exception as e:
        print(f"GraphQL error: {str(e)}")
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
