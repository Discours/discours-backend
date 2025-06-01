import pytest

from services.redis import redis
from tests.test_config import get_test_client


@pytest.fixture(scope="session")
def test_app():
    """Create a test client and session factory."""
    client, session_local = get_test_client()
    return client, session_local


@pytest.fixture
def db_session(test_app):
    """Create a new database session for a test."""
    _, session_local = test_app
    session = session_local()

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
