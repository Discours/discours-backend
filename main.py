from importlib import import_module

from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from auth.authenticate import JWTAuthenticate
from redis import redis
from resolvers.base import resolvers

import_module('resolvers')
schema = make_executable_schema(load_schema_from_path("schema.graphql"), resolvers)

middleware = [Middleware(AuthenticationMiddleware, backend=JWTAuthenticate())]


async def start_up():
    await redis.connect()


async def shutdown():
    await redis.disconnect()


app = Starlette(debug=True, on_startup=[start_up], on_shutdown=[shutdown], middleware=middleware)
app.mount("/", GraphQL(schema, debug=True))
