from functools import wraps
from typing import Optional, Tuple

from graphql import GraphQLResolveInfo
from jwt import DecodeError, ExpiredSignatureError
from starlette.authentication import AuthenticationBackend
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials, AuthUser
from auth.token import Token
from exceptions import InvalidToken, OperationNotAllowed
from orm import User
from redis import redis
from settings import JWT_AUTH_HEADER


class _Authenticate:
	@classmethod
	async def verify(cls, token: str):
		"""
		Rules for a token to be valid.
		1. token format is legal && 
			token exists in redis database && 
			token is not expired
		2. token format is legal &&
			token exists in redis database &&
			token is expired &&
			token is of specified type
		"""
		try:
			payload = Token.decode(token)
		except ExpiredSignatureError:
			payload = Token.decode(token, verify_exp=False)
			if not await cls.exists(payload.user_id, token):
				raise InvalidToken("Login expired, please login again")
			if payload.device == "mobile":  # noqa
				"we cat set mobile token to be valid forever"
				return payload
		except DecodeError as e:
			raise InvalidToken("token format error") from e
		else:
			if not await cls.exists(payload.user_id, token):
				raise InvalidToken("Login expired, please login again")
			return payload

	@classmethod
	async def exists(cls, user_id, token):
		token = await redis.execute("GET", f"{user_id}-{token}")
		return token is not None


class JWTAuthenticate(AuthenticationBackend):
	async def authenticate(
			self, request: HTTPConnection
	) -> Optional[Tuple[AuthCredentials, AuthUser]]:
		if JWT_AUTH_HEADER not in request.headers:
			return AuthCredentials(scopes=[]), AuthUser(user_id=None)

		token = request.headers[JWT_AUTH_HEADER]
		try:
			payload = await _Authenticate.verify(token)
		except Exception as exc:
			return AuthCredentials(scopes=[], error_message=str(exc)), AuthUser(user_id=None)
		
		if payload is None:
			return AuthCredentials(scopes=[]), AuthUser(user_id=None)

		scopes = User.get_permission(user_id=payload.user_id)
		return AuthCredentials(user_id=payload.user_id, scopes=scopes, logged_in=True), AuthUser(user_id=payload.user_id)


def login_required(func):
	@wraps(func)
	async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
		auth: AuthCredentials = info.context["request"].auth
		if not auth.logged_in:
			return {"error" : auth.error_message or "Please login"}
		return await func(parent, info, *args, **kwargs)
	return wrap
