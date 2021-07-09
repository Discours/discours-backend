from importlib import import_module

from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Route

from auth.authenticate import JWTAuthenticate
from auth.oauth import oauth_login, oauth_authorize
from redis import redis
from resolvers.base import resolvers

import_module('resolvers')
schema = make_executable_schema(load_schema_from_path("schema/"), resolvers)

middleware = [
	Middleware(AuthenticationMiddleware, backend=JWTAuthenticate()),
	Middleware(SessionMiddleware, secret_key="!secret")
]

async def start_up():
    await redis.connect()


async def shutdown():
    await redis.disconnect()
    
routes = [
    Route("/oauth", endpoint=oauth_login),
    Route("/authorize", endpoint=oauth_authorize)
]

app = Starlette(debug=True, on_startup=[start_up], on_shutdown=[shutdown], middleware=middleware, routes=routes)
app.mount("/", GraphQL(schema, debug=True))
