from functools import wraps
from typing import Optional, Tuple

from graphql.type import GraphQLResolveInfo
from jwt import DecodeError, ExpiredSignatureError
from starlette.authentication import AuthenticationBackend
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials, AuthUser
from auth.jwtcodec import JWTCodec
from auth.tokenstorage import TokenStorage
from base.exceptions import InvalidToken
from services.auth.users import UserStorage
from settings import SESSION_TOKEN_HEADER


class SessionToken:
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
            print('[auth.authenticate] session token verify')
            payload = JWTCodec.decode(token)
        except ExpiredSignatureError:
            payload = JWTCodec.decode(token, verify_exp=False)
            if not await cls.get(payload.user_id, token):
                raise InvalidToken("Session token has expired, please try again")
        except DecodeError as e:
            raise InvalidToken("token format error") from e
        else:
            if not await cls.get(payload.user_id, token):
                raise InvalidToken("Session token has expired, please login again")
            return payload

    @classmethod
    async def get(cls, uid, token):
        return await TokenStorage.get(f"{uid}-{token}")


class JWTAuthenticate(AuthenticationBackend):
    async def authenticate(
        self, request: HTTPConnection
    ) -> Optional[Tuple[AuthCredentials, AuthUser]]:

        if SESSION_TOKEN_HEADER not in request.headers:
            return AuthCredentials(scopes=[]), AuthUser(user_id=None)

        token = request.headers.get(SESSION_TOKEN_HEADER, "")

        try:
            payload = await SessionToken.verify(token)
        except Exception as exc:
            print("[auth.authenticate] session token verify error")
            print(exc)
            return AuthCredentials(scopes=[], error_message=str(exc)), AuthUser(
                user_id=None
            )

        if payload is None:
            return AuthCredentials(scopes=[]), AuthUser(user_id=None)

        user = await UserStorage.get_user(payload.user_id)
        if not user:
            return AuthCredentials(scopes=[]), AuthUser(user_id=None)

        scopes = await user.get_permission()
        return (
            AuthCredentials(user_id=payload.user_id, scopes=scopes, logged_in=True),
            user,
        )


def login_required(func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        # print('[auth.authenticate] login required for %r with info %r' % (func, info))  # debug only
        auth: AuthCredentials = info.context["request"].auth
        if not auth.logged_in:
            return {"error": auth.error_message or "Please login"}
        return await func(parent, info, *args, **kwargs)

    return wrap
