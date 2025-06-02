import asyncio
import os
from collections.abc import AsyncGenerator
from importlib import import_module
from pathlib import Path
from typing import Any

from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from auth.handler import EnhancedGraphQLHTTPHandler
from auth.middleware import AuthMiddleware, auth_middleware
from auth.oauth import oauth_callback, oauth_login
from cache.precache import precache_data
from cache.revalidator import revalidation_manager
from services.redis import redis
from services.schema import create_all_tables, resolvers
from services.search import check_search_service, initialize_search_index_background, search_service
from services.viewed import ViewedStorage
from settings import DEV_SERVER_PID_FILE_NAME
from utils.logger import root_logger as logger

DEVMODE = os.getenv("DOKKU_APP_TYPE", "false").lower() == "false"
DIST_DIR = Path(__file__).parent / "dist"  # Директория для собранных файлов
INDEX_HTML = Path(__file__).parent / "index.html"

# Импортируем резолверы ПЕРЕД созданием схемы
import_module("resolvers")

# Создаем схему GraphQL
schema = make_executable_schema(load_schema_from_path("schema/"), list(resolvers))

# Создаем middleware с правильным порядком
middleware = [
    # CORS должен быть перед другими middleware для корректной обработки preflight-запросов
    Middleware(
        CORSMiddleware,
        allow_origins=[
            "https://localhost:3000",
            "https://testing.discours.io",
            "https://testing3.discours.io",
            "https://discours.io",
            "https://new.discours.io",
            "https://discours.ru",
            "https://new.discours.ru",
        ],
        allow_methods=["GET", "POST", "OPTIONS"],  # Явно указываем OPTIONS
        allow_headers=["*"],
        allow_credentials=True,
    ),
    # извлечение токена + аутентификация + cookies
    Middleware(AuthMiddleware),
]


# Создаем экземпляр GraphQL с улучшенным обработчиком
graphql_app = GraphQL(schema, debug=DEVMODE, http_handler=EnhancedGraphQLHTTPHandler())


# Оборачиваем GraphQL-обработчик для лучшей обработки ошибок
async def graphql_handler(request: Request) -> Response:
    """
    Обработчик GraphQL запросов с поддержкой middleware и обработкой ошибок.

    Выполняет:
    1. Проверку метода запроса (GET, POST, OPTIONS)
    2. Обработку GraphQL запроса через ariadne
    3. Применение middleware для корректной обработки cookie и авторизации
    4. Обработку исключений и формирование ответа

    Args:
        request: Starlette Request объект

    Returns:
        Response: объект ответа (обычно JSONResponse)
    """
    if request.method not in ["GET", "POST", "OPTIONS"]:
        return JSONResponse({"error": "Method Not Allowed by main.py"}, status_code=405)

    # Проверяем, что все необходимые middleware корректно отработали
    if not hasattr(request, "scope") or "auth" not in request.scope:
        logger.warning("[graphql] AuthMiddleware не обработал запрос перед GraphQL обработчиком")

    try:
        # Обрабатываем запрос через GraphQL приложение
        result = await graphql_app.handle_request(request)

        # Применяем middleware для установки cookie
        # Используем метод process_result из auth_middleware для корректной обработки
        # cookie на основе результатов операций login/logout
        return await auth_middleware.process_result(request, result)
    except asyncio.CancelledError:
        return JSONResponse({"error": "Request cancelled"}, status_code=499)
    except Exception as e:
        logger.error(f"GraphQL error: {e!s}")
        # Логируем более подробную информацию для отладки
        import traceback

        logger.debug(f"GraphQL error traceback: {traceback.format_exc()}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def shutdown() -> None:
    """Остановка сервера и освобождение ресурсов"""
    logger.info("Остановка сервера")

    # Закрываем соединение с Redis
    await redis.disconnect()

    # Останавливаем поисковый сервис
    search_service.close()

    # Удаляем PID-файл, если он существует
    from settings import DEV_SERVER_PID_FILE_NAME

    pid_file = Path(DEV_SERVER_PID_FILE_NAME)
    if pid_file.exists():
        pid_file.unlink()


async def dev_start() -> None:
    """
    Инициализация сервера в DEV режиме.

    Функция:
    1. Проверяет наличие DEV режима
    2. Создает PID-файл для отслеживания процесса
    3. Логирует информацию о старте сервера

    Используется только при запуске сервера с флагом "dev".
    """
    try:
        pid_path = Path(DEV_SERVER_PID_FILE_NAME)
        # Если PID-файл уже существует, проверяем, не запущен ли уже сервер с этим PID
        if pid_path.exists():
            try:
                with pid_path.open(encoding="utf-8") as f:
                    old_pid = int(f.read().strip())
                # Проверяем, существует ли процесс с таким PID

                try:
                    os.kill(old_pid, 0)  # Сигнал 0 только проверяет существование процесса
                    print(f"[warning] DEV server already running with PID {old_pid}")
                except OSError:
                    print(f"[info] Stale PID file found, previous process {old_pid} not running")
            except (ValueError, FileNotFoundError):
                print("[warning] Invalid PID file found, recreating")

        # Создаем или перезаписываем PID-файл
        with pid_path.open("w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        print(f"[main] process started in DEV mode with PID {os.getpid()}")
    except Exception as e:
        logger.error(f"[main] Error during server startup: {e!s}")
        # Не прерываем запуск сервера из-за ошибки в этой функции
        print(f"[warning] Error during DEV mode initialization: {e!s}")


# Глобальная переменная для background tasks
background_tasks = []


async def lifespan(_app: Any) -> AsyncGenerator[None, None]:
    """
    Функция жизненного цикла приложения.

    Обеспечивает:
    1. Инициализацию всех необходимых сервисов и компонентов
    2. Предзагрузку кеша данных
    3. Подключение к Redis и поисковому сервису
    4. Корректное завершение работы при остановке сервера

    Args:
        _app: экземпляр Starlette приложения

    Yields:
        None: генератор для управления жизненным циклом
    """
    try:
        print("[lifespan] Starting application initialization")
        create_all_tables()
        await asyncio.gather(
            redis.connect(),
            precache_data(),
            ViewedStorage.init(),
            check_search_service(),
            revalidation_manager.start(),
        )
        if DEVMODE:
            await dev_start()
        print("[lifespan] Basic initialization complete")

        # Add a delay before starting the intensive search indexing
        print("[lifespan] Waiting for system stabilization before search indexing...")
        await asyncio.sleep(10)  # 10-second delay to let the system stabilize

        # Start search indexing as a background task with lower priority
        search_task = asyncio.create_task(initialize_search_index_background())
        background_tasks.append(search_task)
        # Не ждем завершения задачи, позволяем ей выполняться в фоне

        yield
    finally:
        print("[lifespan] Shutting down application services")

        # Отменяем все background tasks
        for task in background_tasks:
            if not task.done():
                task.cancel()

        # Ждем завершения отмены tasks
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        tasks = [redis.disconnect(), ViewedStorage.stop(), revalidation_manager.stop()]
        await asyncio.gather(*tasks, return_exceptions=True)
        print("[lifespan] Shutdown complete")


# Обновляем маршрут в Starlette
app = Starlette(
    routes=[
        Route("/graphql", graphql_handler, methods=["GET", "POST", "OPTIONS"]),
        # OAuth маршруты
        Route("/oauth/{provider}", oauth_login, methods=["GET"]),
        Route("/oauth/{provider}/callback", oauth_callback, methods=["GET"]),
        Mount("/", app=StaticFiles(directory=str(DIST_DIR), html=True)),
    ],
    lifespan=lifespan,
    middleware=middleware,  # Явно указываем список middleware
    debug=True,
)

if DEVMODE:
    # Для DEV режима регистрируем дополнительный CORS middleware только для localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
