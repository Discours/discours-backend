from functools import wraps
from typing import Optional, Tuple
from datetime import datetime, timedelta
from graphql import GraphQLResolveInfo
from jwt import DecodeError, ExpiredSignatureError
from starlette.authentication import AuthenticationBackend
from starlette.requests import HTTPConnection
from auth.credentials import AuthCredentials, AuthUser
from auth.jwtcodec import JWTCodec
from auth.authorize import Authorize, TokenStorage
from base.exceptions import InvalidToken
from orm.user import User
from services.auth.users import UserStorage
from base.orm import local_session
from settings import JWT_AUTH_HEADER, EMAIL_TOKEN_LIFE_SPAN


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
			payload = JWTCodec.decode(token)
		except ExpiredSignatureError:
			payload = JWTCodec.decode(token, verify_exp=False)
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
		return await TokenStorage.exist(f"{user_id}-{token}")


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

		if not payload.device in ("pc", "mobile"):
			return AuthCredentials(scopes=[]), AuthUser(user_id=None)

		user = await UserStorage.get_user(payload.user_id)
		if not user:
			return AuthCredentials(scopes=[]), AuthUser(user_id=None)

		scopes = await user.get_permission()
		return AuthCredentials(user_id=payload.user_id, scopes=scopes, logged_in=True), user

class EmailAuthenticate:
	@staticmethod
	async def get_email_token(user):
		token = await Authorize.authorize(
			user,
			device="email",
			life_span=EMAIL_TOKEN_LIFE_SPAN
			)
		return token

	@staticmethod
	async def authenticate(token):
		payload = await _Authenticate.verify(token)
		if payload is None:
			raise InvalidToken("invalid token")
		if payload.device != "email":
			raise InvalidToken("invalid token")
		with local_session() as session:
			user = session.query(User).filter_by(id=payload.user_id).first()
			if not user:
				raise Exception("user not exist")
			if not user.emailConfirmed:
				user.emailConfirmed = True
				session.commit()
		auth_token = await Authorize.authorize(user)
		return (auth_token, user)

class ResetPassword:
	@staticmethod
	async def get_reset_token(user):
		exp = datetime.utcnow() + timedelta(seconds=EMAIL_TOKEN_LIFE_SPAN)
		token = JWTCodec.encode(user, exp=exp, device="pc")
		await TokenStorage.save(f"{user.id}-reset-{token}", EMAIL_TOKEN_LIFE_SPAN, True)
		return token

	@staticmethod
	async def verify(token):
		try:
			payload = JWTCodec.decode(token)
		except ExpiredSignatureError:
			raise InvalidToken("Login expired, please login again")
		except DecodeError as e:
			raise InvalidToken("token format error") from e
		else:
			if not await TokenStorage.exist(f"{payload.user_id}-reset-{token}"):
				raise InvalidToken("Login expired, please login again")

		return payload.user_id

def login_required(func):
	@wraps(func)
	async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
		auth: AuthCredentials = info.context["request"].auth
		if not auth.logged_in:
			return {"error" : auth.error_message or "Please login"}
		return await func(parent, info, *args, **kwargs)
	return wrap
