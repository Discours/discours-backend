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

from auth.authenticate import JWTAuthenticate
from auth.oauth import oauth_authorize, oauth_login
from base.redis import redis
from base.resolvers import resolvers
from orm import init_tables
from resolvers.auth import confirm_email_handler
from resolvers.upload import upload_handler
from services.main import storages_init
from services.notifications.notification_service import notification_service
from services.notifications.sse import sse_subscribe_handler
from services.stat.viewed import ViewedStorage
# from services.zine.gittask import GitTask
from settings import DEV_SERVER_PID_FILE_NAME, SENTRY_DSN, SESSION_SECRET_KEY

import_module("resolvers")
schema = make_executable_schema(load_schema_from_path("schema.graphql"), resolvers)  # type: ignore

middleware = [
    Middleware(AuthenticationMiddleware, backend=JWTAuthenticate()),
    Middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY),
]


async def start_up():
    init_tables()
    await redis.connect()
    await storages_init()
    views_stat_task = asyncio.create_task(ViewedStorage().worker())
    print(views_stat_task)
    # git_task = asyncio.create_task(GitTask.git_task_worker())
    # print(git_task)
    notification_service_task = asyncio.create_task(notification_service.worker())
    print(notification_service_task)

    try:
        import sentry_sdk

        sentry_sdk.init(SENTRY_DSN)
    except Exception as e:
        print('[sentry] init error')
        print(e)


async def dev_start_up():
    if exists(DEV_SERVER_PID_FILE_NAME):
        await redis.connect()
        return
    else:
        with open(DEV_SERVER_PID_FILE_NAME, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))

    await start_up()


async def shutdown():
    await redis.disconnect()


routes = [
    # Route("/messages", endpoint=sse_messages),
    Route("/oauth/{provider}", endpoint=oauth_login),
    Route("/oauth-authorize", endpoint=oauth_authorize),
    Route("/confirm/{token}", endpoint=confirm_email_handler),
    Route("/upload", endpoint=upload_handler, methods=['POST']),
    Route("/subscribe/{user_id}", endpoint=sse_subscribe_handler),
]

app = Starlette(
    on_startup=[start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
app.mount("/", GraphQL(schema))

dev_app = Starlette(
    debug=True,
    on_startup=[dev_start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
dev_app.mount("/", GraphQL(schema, debug=True))
