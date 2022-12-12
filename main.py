import asyncio
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
from base.redis import redis
from base.resolvers import resolvers
from resolvers.auth import confirm_email_handler
from services.main import storages_init
from services.stat.viewed import ViewedStorage
from services.zine.gittask import GitTask
from settings import DEV_SERVER_STATUS_FILE_NAME, SENTRY_DSN
# from sse.transport import GraphQLSSEHandler
# from services.inbox.presence import on_connect, on_disconnect
from services.inbox.sse import sse_messages


import_module("resolvers")
schema = make_executable_schema(load_schema_from_path("schema.graphql"), resolvers)  # type: ignore

middleware = [
    Middleware(AuthenticationMiddleware, backend=JWTAuthenticate()),
    Middleware(SessionMiddleware, secret_key="!secret"),
]


async def start_up():
    init_tables()
    await redis.connect()
    await storages_init()
    views_stat_task = asyncio.create_task(ViewedStorage().worker())
    print(views_stat_task)
    git_task = asyncio.create_task(GitTask.git_task_worker())
    print(git_task)
    try:
        import sentry_sdk
        sentry_sdk.init(SENTRY_DSN)
    except Exception as e:
        print('[sentry] init error')
        print(e)


async def dev_start_up():
    if exists(DEV_SERVER_STATUS_FILE_NAME):
        await redis.connect()
        return
    else:
        with open(DEV_SERVER_STATUS_FILE_NAME, 'w', encoding='utf-8') as f:
            f.write('running')

    await start_up()


async def shutdown():
    await redis.disconnect()


routes = [
    Route("/oauth/{provider}", endpoint=oauth_login),
    Route("/oauth-authorize", endpoint=oauth_authorize),
    Route("/confirm/{token}", endpoint=confirm_email_handler),
    Route("/messages", endpoint=sse_messages)
]

app = Starlette(
    debug=True,
    on_startup=[start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
app.mount("/graphql", GraphQL(
    schema,
    debug=True,
    # websocket_handler=GraphQLTransportWSHandler(
    #    on_connect=on_connect,
    #    on_disconnect=on_disconnect
    # )
))

dev_app = app = Starlette(
    debug=True,
    on_startup=[dev_start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
dev_app.mount("/graphql", GraphQL(
    schema,
    debug=True,
    # websocket_handler=GraphQLTransportWSHandler(
    #    on_connect=on_connect,
    #    on_disconnect=on_disconnect
    # )
))
