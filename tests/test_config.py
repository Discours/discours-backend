"""
Конфигурация для тестов
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.testclient import TestClient

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
    from services.db import Base

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
    SessionLocal = sessionmaker(bind=engine)

    # Создаем middleware для сессий
    middleware = [Middleware(DatabaseMiddleware, session_maker=SessionLocal)]

    # Создаем тестовое приложение
    app = Starlette(
        debug=True,
        middleware=middleware,
        routes=[],  # Здесь можно добавить тестовые маршруты если нужно
    )

    return app, SessionLocal


def get_test_client():
    """Get a test client with initialized database."""
    app, SessionLocal = create_test_app()
    return TestClient(app), SessionLocal
