import asyncio
import os
from importlib import import_module
from os.path import exists
from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Route
from orm import init_tables

from auth.authenticate import JWTAuthenticate
from auth.oauth import oauth_login, oauth_authorize
from services.redis import redis
from services.schema import resolvers
from resolvers.auth import confirm_email_handler
from resolvers.upload import upload_handler
from settings import DEV_SERVER_PID_FILE_NAME, SENTRY_DSN
from services.search import SearchService
from services.viewed import ViewedStorage
from services.db import local_session

import_module("resolvers")
schema = make_executable_schema(load_schema_from_path("schemas/core.graphql"), resolvers)  # type: ignore
middleware = [
    Middleware(AuthenticationMiddleware, backend=JWTAuthenticate()),
    Middleware(SessionMiddleware, secret_key="!secret"),
]


async def start_up():
    init_tables()
    await redis.connect()
    with local_session() as session:
        await SearchService.init(session)
    await ViewedStorage.init()
    _views_stat_task = asyncio.create_task(ViewedStorage().worker())
    try:
        import sentry_sdk

        sentry_sdk.init(SENTRY_DSN)
        print("[sentry] started")
    except Exception as e:
        print("[sentry] init error")
        print(e)

    print("[main] started")


async def dev_start_up():
    if exists(DEV_SERVER_PID_FILE_NAME):
        await redis.connect()
        return
    else:
        with open(DEV_SERVER_PID_FILE_NAME, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

    await start_up()


async def shutdown():
    await redis.disconnect()


routes = [
    Route("/oauth/{provider}", endpoint=oauth_login),
    Route("/oauth-authorize", endpoint=oauth_authorize),
    Route("/confirm/{token}", endpoint=confirm_email_handler),
    Route("/upload", endpoint=upload_handler, methods=["POST"]),
]

app = Starlette(
    debug=True,
    on_startup=[start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
app.mount(
    "/",
    GraphQL(schema, debug=True),
)

dev_app = app = Starlette(
    debug=True,
    on_startup=[dev_start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
dev_app.mount(
    "/",
    GraphQL(schema, debug=True),
)
