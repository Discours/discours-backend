from functools import wraps
from typing import Optional

from graphql.type import GraphQLResolveInfo
from sqlalchemy.orm import exc
from starlette.authentication import AuthenticationBackend
from starlette.requests import HTTPConnection

from auth.credentials import AuthCredentials
from auth.exceptions import OperationNotAllowed
from auth.sessions import SessionManager
from auth.orm import Author
from services.db import local_session
from settings import SESSION_TOKEN_HEADER


class JWTAuthenticate(AuthenticationBackend):
    async def authenticate(self, request: HTTPConnection) -> Optional[AuthCredentials]:
        """
        Аутентификация пользователя по JWT токену.

        Args:
            request: HTTP запрос

        Returns:
            AuthCredentials при успешной аутентификации или None при ошибке
        """
        if SESSION_TOKEN_HEADER not in request.headers:
            return None

        auth_header = request.headers.get(SESSION_TOKEN_HEADER)
        if not auth_header:
            print("[auth.authenticate] no token in header %s" % SESSION_TOKEN_HEADER)
            return None

        # Обработка формата "Bearer <token>"
        token = auth_header
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "", 1).strip()

        if not token:
            print("[auth.authenticate] empty token after Bearer prefix removal")
            return None

        # Проверяем сессию в Redis
        payload = await SessionManager.verify_session(token)
        if not payload:
            return None

        with local_session() as session:
            try:
                author = (
                    session.query(Author)
                    .filter(Author.id == payload.user_id)
                    .filter(Author.is_active == True)  # noqa
                    .one()
                )

                if author.is_locked():
                    return None

                # Получаем разрешения из ролей
                scopes = author.get_permissions()

                return AuthCredentials(
                    author_id=author.id, scopes=scopes, logged_in=True, email=author.email
                )
            except exc.NoResultFound:
                return None


def login_required(func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        auth: AuthCredentials = info.context["request"].auth
        if not auth or not auth.logged_in:
            return {"error": "Please login first"}
        return await func(parent, info, *args, **kwargs)

    return wrap


def permission_required(resource: str, operation: str, func):
    """
    Декоратор для проверки разрешений.

    Args:
        resource (str): Ресурс для проверки
        operation (str): Операция для проверки
        func: Декорируемая функция
    """

    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        auth: AuthCredentials = info.context["request"].auth
        if not auth.logged_in:
            raise OperationNotAllowed(auth.error_message or "Please login")

        with local_session() as session:
            author = session.query(Author).filter(Author.id == auth.author_id).one()

            # Проверяем базовые условия
            if not author.is_active:
                raise OperationNotAllowed("Account is not active")
            if author.is_locked():
                raise OperationNotAllowed("Account is locked")

            # Проверяем разрешение
            if not author.has_permission(resource, operation):
                raise OperationNotAllowed(f"No permission for {operation} on {resource}")

        return await func(parent, info, *args, **kwargs)

    return wrap


def login_accepted(func):
    @wraps(func)
    async def wrap(parent, info: GraphQLResolveInfo, *args, **kwargs):
        auth: AuthCredentials = info.context["request"].auth

        if auth and auth.logged_in:
            with local_session() as session:
                author = session.query(Author).filter(Author.id == auth.author_id).one()
                info.context["author"] = author.dict()
                info.context["user_id"] = author.id
        else:
            info.context["author"] = None
            info.context["user_id"] = None

        return await func(parent, info, *args, **kwargs)

    return wrap
