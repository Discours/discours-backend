import asyncio
import os
import sys
from importlib import import_module
from os.path import exists

from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from cache.precache import precache_data
from cache.revalidator import revalidation_manager
from services.exception import ExceptionHandlerMiddleware
from services.redis import redis
from services.schema import create_all_tables, resolvers
from services.search import search_service, initialize_search_index
from services.viewed import ViewedStorage
from services.webhook import WebhookEndpoint, create_webhook_endpoint
from settings import DEV_SERVER_PID_FILE_NAME, MODE

import_module("resolvers")
schema = make_executable_schema(load_schema_from_path("schema/"), resolvers)


async def start():
    if MODE == "development":
        if not exists(DEV_SERVER_PID_FILE_NAME):
            # pid file management
            with open(DEV_SERVER_PID_FILE_NAME, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
    print(f"[main] process started in {MODE} mode")

async def check_search_service():
    """Check if search service is available and log result"""
    info = await search_service.info()
    if info.get("status") in ["error", "unavailable"]:
        print(f"[WARNING] Search service unavailable: {info.get('message', 'unknown reason')}")
    else:
        print(f"[INFO] Search service is available: {info}")

# Helper to run precache with timeout and catch errors
async def precache_with_timeout():
    try:
        await asyncio.wait_for(precache_data(), timeout=60)
    except asyncio.TimeoutError:
        print("[precache] Precache timed out after 60 seconds")
    except Exception as e:
        print(f"[precache] Error during precache: {e}")


# indexing DB data
# async def indexing():
#     from services.db import fetch_all_shouts
#     all_shouts = await fetch_all_shouts()
#     await initialize_search_index(all_shouts)
async def lifespan(_app):
    try:
        print("[lifespan] Starting application initialization")
        create_all_tables()
        
        # schedule precaching in background with timeout and error handling
        asyncio.create_task(precache_with_timeout())
        
        await asyncio.gather(
            redis.connect(),
            ViewedStorage.init(),
            create_webhook_endpoint(),
            check_search_service(),
            start(),
            revalidation_manager.start(),
        )
        print("[lifespan] Basic initialization complete")

        # Add a delay before starting the intensive search indexing
        print("[lifespan] Waiting for system stabilization before search indexing...")
        await asyncio.sleep(10)  # 10-second delay to let the system stabilize

        # Start search indexing as a background task with lower priority
        asyncio.create_task(initialize_search_index_background())

        yield
    finally:
        print("[lifespan] Shutting down application services")
        tasks = [redis.disconnect(), ViewedStorage.stop(), revalidation_manager.stop()]
        await asyncio.gather(*tasks, return_exceptions=True)
        print("[lifespan] Shutdown complete")

# Initialize search index in the background
async def initialize_search_index_background():
    """Run search indexing as a background task with low priority"""
    try:
        print("[search] Starting background search indexing process")
        from services.db import fetch_all_shouts
        
        # Get total count first (optional)
        all_shouts = await fetch_all_shouts()
        total_count = len(all_shouts) if all_shouts else 0
        print(f"[search] Fetched {total_count} shouts for background indexing")
        
        # Start the indexing process with the fetched shouts
        print("[search] Beginning background search index initialization...")
        await initialize_search_index(all_shouts)
        print("[search] Background search index initialization complete")
    except Exception as e:
        print(f"[search] Error in background search indexing: {str(e)}")

# Создаем экземпляр GraphQL
graphql_app = GraphQL(schema, debug=True)


# Оборачиваем GraphQL-обработчик для лучшей обработки ошибок
async def graphql_handler(request: Request):
    if request.method not in ["GET", "POST"]:
        return JSONResponse({"error": "Method Not Allowed"}, status_code=405)

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


# Обновляем маршрут в Starlette
app = Starlette(
    routes=[
        Route("/", graphql_handler, methods=["GET", "POST"]),
        Route("/new-author", WebhookEndpoint),
    ],
    lifespan=lifespan,
    debug=True,
)

app.add_middleware(ExceptionHandlerMiddleware)
if "dev" in sys.argv:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
