"""
Конфигурация для тестов
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Route
from starlette.testclient import TestClient

# Импортируем все модели чтобы SQLAlchemy знал о них
from auth.orm import (  # noqa: F401
    Author,
    AuthorBookmark,
    AuthorFollower,
    AuthorRating
)
from orm.collection import ShoutCollection  # noqa: F401
from orm.community import Community, CommunityAuthor, CommunityFollower  # noqa: F401
from orm.draft import Draft, DraftAuthor, DraftTopic  # noqa: F401
from orm.invite import Invite  # noqa: F401
from orm.notification import Notification  # noqa: F401
from orm.shout import Shout, ShoutReactionsFollower, ShoutTopic  # noqa: F401
from orm.topic import Topic, TopicFollower  # noqa: F401

# Используем in-memory SQLite для тестов
TEST_DB_URL = "sqlite:///:memory:"


class DatabaseMiddleware(BaseHTTPMiddleware):
    """Middleware для внедрения сессии БД"""

    def __init__(self, app, session_maker):
        super().__init__(app)
        self.session_maker = session_maker

    async def dispatch(self, request, call_next):
        session = self.session_maker()
        request.state.db = session
        try:
            response = await call_next(request)
        finally:
            session.close()
        return response


def create_test_app():
    """Create a test Starlette application."""
    from importlib import import_module

    from ariadne import load_schema_from_path, make_executable_schema
    from ariadne.asgi import GraphQL
    from starlette.responses import JSONResponse

    from services.db import Base
    from services.schema import resolvers

    # Создаем движок и таблицы
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Создаем фабрику сессий
    session_local = sessionmaker(bind=engine)

    # Импортируем резолверы для GraphQL
    import_module("resolvers")

    # Создаем схему GraphQL
    schema = make_executable_schema(load_schema_from_path("schema/"), list(resolvers))

    # Создаем кастомный GraphQL класс для тестов
    class TestGraphQL(GraphQL):
        async def get_context_for_request(self, request, data):
            """Переопределяем контекст для тестов"""
            context = {
                "request": None,  # Устанавливаем None для активации тестового режима
                "author": None,
                "roles": [],
            }

            # Для тестов, если есть заголовок авторизации, создаем мок пользователя
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # Простая мок авторизация для тестов - создаем пользователя с ID 1
                context["author"] = {"id": 1, "name": "Test User"}
                context["roles"] = ["reader", "author"]

            return context

    # Создаем GraphQL приложение с кастомным классом
    graphql_app = TestGraphQL(schema, debug=True)

    async def graphql_handler(request):
        """Простой GraphQL обработчик для тестов"""
        try:
            return await graphql_app.handle_request(request)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # Создаем middleware для сессий
    middleware = [Middleware(DatabaseMiddleware, session_maker=session_local)]

    # Создаем тестовое приложение с GraphQL маршрутом
    app = Starlette(
        debug=True,
        middleware=middleware,
        routes=[
            Route("/", graphql_handler, methods=["GET", "POST"]),  # Основной GraphQL эндпоинт
            Route("/graphql", graphql_handler, methods=["GET", "POST"]),  # Альтернативный путь
        ],
    )

    return app, session_local


def get_test_client():
    """Get a test client with initialized database."""
    app, session_local = create_test_app()
    return TestClient(app), session_local
