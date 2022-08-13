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
from auth.email import email_authorize
from base.redis import redis
from base.resolvers import resolvers
from resolvers.zine import ShoutsCache
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage
from services.zine.gittask import GitTask
from services.stat.topicstat import TopicStat
from services.zine.shoutauthor import ShoutAuthorStorage
import asyncio

import_module('resolvers')
schema = make_executable_schema(load_schema_from_path("schema.graphql"), resolvers)

middleware = [
	Middleware(AuthenticationMiddleware, backend=JWTAuthenticate()),
	Middleware(SessionMiddleware, secret_key="!secret")
]

async def start_up():
	await redis.connect()
	viewed_storage_task = asyncio.create_task(ViewedStorage.worker())
	reacted_storage_task = asyncio.create_task(ReactedStorage.worker())
	shouts_cache_task = asyncio.create_task(ShoutsCache.worker())
	shout_author_task = asyncio.create_task(ShoutAuthorStorage.worker())
	topic_stat_task = asyncio.create_task(TopicStat.worker())
	git_task = asyncio.create_task(GitTask.git_task_worker())

async def shutdown():
	await redis.disconnect()

routes = [
	Route("/oauth/{provider}", endpoint=oauth_login),
	Route("/oauth_authorize", endpoint=oauth_authorize),
	Route("/email_authorize", endpoint=email_authorize)
]

app = Starlette(debug=True, on_startup=[start_up], on_shutdown=[shutdown], middleware=middleware, routes=routes)
app.mount("/", GraphQL(schema, debug=True))
