from functools import wraps
from typing import Optional, Tuple

from graphql.type import GraphQLResolveInfo
from starlette.authentication import AuthenticationBackend
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials, AuthUser
from services.auth.users import UserStorage
from settings import SESSION_TOKEN_HEADER
from auth.tokenstorage import SessionToken
from base.exceptions import InvalidToken


class JWTAuthenticate(AuthenticationBackend):
    async def authenticate(
        self, request: HTTPConnection
    ) -> Optional[Tuple[AuthCredentials, AuthUser]]:

        if SESSION_TOKEN_HEADER not in request.headers:
            return AuthCredentials(scopes=[]), AuthUser(user_id=None)

        token = request.headers.get(SESSION_TOKEN_HEADER)
        if not token:
            print("[auth.authenticate] no token in header %s" % SESSION_TOKEN_HEADER)
            return AuthCredentials(scopes=[], error_message=str("no token")), AuthUser(
                user_id=None
            )

        try:
            if len(token.split('.')) > 1:
                payload = await SessionToken.verify(token)
            else:
                InvalidToken("please try again")
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


def permission_required(resource, operation, func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        # print('[auth.authenticate] login required for %r with info %r' % (func, info))  # debug only
        auth: AuthCredentials = info.context["request"].auth
        if not auth.logged_in:
            return {"error": auth.error_message or "Please login"}

        # TODO: add check permission logix

        return await func(parent, info, *args, **kwargs)

    return wrap
