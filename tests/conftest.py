import asyncio
import pytest
from services.redis import redis
from tests.test_config import get_test_client


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_app():
    """Create a test client and session factory."""
    client, SessionLocal = get_test_client()
    return client, SessionLocal


@pytest.fixture
def db_session(test_app):
    """Create a new database session for a test."""
    _, SessionLocal = test_app
    session = SessionLocal()

    yield session

    session.rollback()
    session.close()


@pytest.fixture
def test_client(test_app):
    """Get the test client."""
    client, _ = test_app
    return client


@pytest.fixture
async def redis_client():
    """Create a test Redis client."""
    await redis.connect()
    await redis.flushall()  # Очищаем Redis перед каждым тестом
    yield redis
    await redis.flushall()  # Очищаем после теста
    await redis.disconnect()
