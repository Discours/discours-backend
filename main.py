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
from starlette.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from cache.precache import precache_data
from cache.revalidator import revalidation_manager
from services.exception import ExceptionHandlerMiddleware
from services.redis import redis
from services.schema import create_all_tables, resolvers
from services.search import search_service

from settings import DEV_SERVER_PID_FILE_NAME, MODE, ADMIN_EMAILS
from utils.logger import root_logger as logger
from auth.internal import InternalAuthentication
from auth import routes as auth_routes  # Импортируем маршруты авторизации
from auth.middleware import (
    AuthorizationMiddleware,
    GraphQLExtensionsMiddleware,
)  # Импортируем middleware для авторизации

import_module("resolvers")
import_module("auth.resolvers")

# Создаем схему GraphQL
schema = make_executable_schema(load_schema_from_path("schema/"), resolvers)

# Пути к клиентским файлам
CLIENT_DIR = join(os.path.dirname(__file__), "client")
DIST_DIR = join(os.path.dirname(__file__), "dist")  # Директория для собранных файлов
INDEX_HTML = join(os.path.dirname(__file__), "index.html")


async def index_handler(request: Request):
    """
    Раздача основного HTML файла
    """
    return FileResponse(INDEX_HTML)


# GraphQL API
class CustomGraphQLHTTPHandler(GraphQLHTTPHandler):
    """
    Кастомный GraphQL HTTP обработчик, который добавляет объект response в контекст
    """

    async def get_context_for_request(self, request: Request, data: dict) -> dict:
        """
        Переопределяем метод для добавления объекта response и extensions в контекст
        """
        context = await super().get_context_for_request(request, data)
        # Создаем объект ответа, который будем использовать для установки cookie
        response = JSONResponse({})
        context["response"] = response

        # Добавляем extensions в контекст
        if "extensions" not in context:
            context["extensions"] = GraphQLExtensionsMiddleware()

        return context


graphql_app = GraphQL(schema, debug=MODE == "development", http_handler=CustomGraphQLHTTPHandler())


async def graphql_handler(request):
    """Обработчик GraphQL запросов"""
    # Проверяем заголовок Content-Type
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json") and "application/json" in request.headers.get(
        "accept", ""
    ):
        # Если не application/json, но клиент принимает JSON
        request._headers["content-type"] = "application/json"

    # Обрабатываем GraphQL запрос
    result = await graphql_app.handle_request(request)

    # Если result - это ответ от сервера, возвращаем его как есть
    if hasattr(result, "body"):
        return result

    # Если результат - это словарь, значит нужно его сконвертировать в JSONResponse
    if isinstance(result, dict):
        return JSONResponse(result)

    return result


async def admin_handler(request: Request):
    """
    Обработчик для маршрута /admin с серверной проверкой прав доступа
    """
    # Проверяем авторизован ли пользователь
    if not request.user.is_authenticated:
        # Если пользователь не авторизован, перенаправляем на главную страницу
        return RedirectResponse(url="/", status_code=303)
    
    # Проверяем является ли пользователь администратором
    auth = getattr(request, "auth", None)
    is_admin = False
    
    # Проверяем наличие объекта auth и метода is_admin
    if auth:
        try:
            # Проверяем имеет ли пользователь права администратора
            is_admin = auth.is_admin
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора: {e}")
    
    # Дополнительная проверка email (для случаев, когда нет метода is_admin)
    admin_emails = ADMIN_EMAILS.split(",")
    if not is_admin and hasattr(auth, "email") and auth.email in admin_emails:
        is_admin = True
    
    if is_admin:
        # Если пользователь - администратор, возвращаем HTML-файл
        return FileResponse(INDEX_HTML)
    else:
        # Для авторизованных пользователей без прав администратора показываем страницу с ошибкой доступа
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Доступ запрещен</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f5f5f5; }
                    .error-container { max-width: 500px; padding: 30px; background-color: #fff; border-radius: 5px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1); text-align: center; }
                    h1 { color: #e74c3c; margin-bottom: 20px; }
                    p { color: #333; margin-bottom: 20px; line-height: 1.5; }
                    .back-button { background-color: #3498db; color: #fff; border: none; padding: 10px 20px; border-radius: 3px; cursor: pointer; text-decoration: none; display: inline-block; }
                    .back-button:hover { background-color: #2980b9; }
                </style>
            </head>
            <body>
                <div class="error-container">
                    <h1>Доступ запрещен</h1>
                    <p>У вас нет прав для доступа к административной панели. Обратитесь к администратору системы для получения необходимых разрешений.</p>
                    <a href="/" class="back-button">Вернуться на главную</a>
                </div>
            </body>
            </html>
            """,
            status_code=403
        )


# Функция запуска сервера
async def start():
    """Запуск сервера и инициализация данных"""
    logger.info(f"Запуск сервера в режиме: {MODE}")

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
    if exists(DEV_SERVER_PID_FILE_NAME):
        os.unlink(DEV_SERVER_PID_FILE_NAME)


# Добавляем маршруты статических файлов, если директория существует
routes = []
if exists(DIST_DIR):
    routes.append(Mount("/", app=StaticFiles(directory=DIST_DIR, html=True)))
    
# Маршруты для API и веб-приложения
routes.extend(
    [
        Route("/graphql", graphql_handler, methods=["GET", "POST"]),
        # Добавляем специальный маршрут для админ-панели с проверкой прав доступа
        Route("/admin", admin_handler, methods=["GET"]),
        # Маршрут для обработки всех остальных запросов - SPA
        Route("/{path:path}", index_handler, methods=["GET"]),
        Route("/", index_handler, methods=["GET"]),
    ]
)

# Добавляем маршруты авторизации
routes.extend(auth_routes)

app = Starlette(
    debug=MODE == "development",
    routes=routes,
    middleware=[
        Middleware(ExceptionHandlerMiddleware),
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        ),
        # Добавляем middleware для обработки Authorization заголовка с Bearer токеном
        Middleware(AuthorizationMiddleware),
        # Добавляем middleware для аутентификации после обработки токенов
        Middleware(AuthenticationMiddleware, backend=InternalAuthentication()),
    ],
    on_startup=[start],
    on_shutdown=[shutdown],
)
