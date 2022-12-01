from functools import wraps
from typing import Optional, Tuple

from graphql.type import GraphQLResolveInfo
from sqlalchemy.orm import joinedload, exc
from starlette.authentication import AuthenticationBackend
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials, AuthUser
from base.orm import local_session
from orm.user import User, Role

from settings import SESSION_TOKEN_HEADER
from auth.tokenstorage import SessionToken
from base.exceptions import InvalidToken, Unauthorized, OperationNotAllowed


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
                if payload is None:
                    return AuthCredentials(scopes=[]), AuthUser(user_id=None)

                with local_session() as session:
                    try:
                        user = (
                            session.query(User).options(
                                joinedload(User.roles).options(joinedload(Role.permissions)),
                                joinedload(User.ratings)
                            ).filter(
                                User.id == payload.user_id
                            ).one()
                        )
                    except exc.NoResultFound:
                        user = None

                if not user:
                    return AuthCredentials(scopes=[]), AuthUser(user_id=None)

                scopes = user.get_permission()

                return (
                    AuthCredentials(
                        user_id=payload.user_id,
                        scopes=scopes,
                        logged_in=True
                    ),
                    AuthUser(user_id=user.id),
                )
            else:
                InvalidToken("please try again")
        except Exception as e:
            print("[auth.authenticate] session token verify error")
            print(e)
            return AuthCredentials(scopes=[], error_message=str(e)), AuthUser(user_id=None)


def login_required(func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        # print('[auth.authenticate] login required for %r with info %r' % (func, info))  # debug only
        auth: AuthCredentials = info.context["request"].auth
        # print(auth)
        if not auth or not auth.logged_in:
            raise Unauthorized(auth.error_message or "Please login")
        return await func(parent, info, *args, **kwargs)

    return wrap


def permission_required(resource, operation, func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        print('[auth.authenticate] permission_required for %r with info %r' % (func, info))  # debug only
        auth: AuthCredentials = info.context["request"].auth
        if not auth.logged_in:
            raise OperationNotAllowed(auth.error_message or "Please login")

        # TODO: add actual check permission logix here

        return await func(parent, info, *args, **kwargs)

    return wrap
