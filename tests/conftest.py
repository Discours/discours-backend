import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orm.base import BaseModel as Base
from services.redis import redis
from tests.test_config import get_test_client


@pytest.fixture(scope="session")
def test_engine():
    """
    Создает тестовый engine для всей сессии тестирования.
    Использует in-memory SQLite для быстрых тестов.
    """
    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    # Создаем все таблицы
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup после всех тестов
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    """
    Создает фабрику сессий для тестирования.
    """
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture
def db_session(test_session_factory):
    """
    Создает новую сессию БД для каждого теста.
    Простая реализация без вложенных транзакций.
    """
    session = test_session_factory()

    # Создаем дефолтное сообщество для тестов
    from orm.community import Community
    from auth.orm import Author
    import time

    # Создаем системного автора если его нет
    system_author = session.query(Author).filter(Author.slug == "system").first()
    if not system_author:
        system_author = Author(
            name="System",
            slug="system",
            email="system@test.local",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            last_seen=int(time.time())
        )
        session.add(system_author)
        session.flush()

    # Создаем дефолтное сообщество если его нет
    default_community = session.query(Community).filter(Community.id == 1).first()
    if not default_community:
        default_community = Community(
            id=1,
            name="Главное сообщество",
            slug="main",
            desc="Основное сообщество для тестов",
            pic="",
            created_at=int(time.time()),
            created_by=system_author.id,
            settings={"default_roles": ["reader", "author"], "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"]},
            private=False
        )
        session.add(default_community)
        session.commit()

    yield session

    # Очищаем все данные после теста
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def db_session_commit(test_session_factory):
    """
    Создает сессию БД с реальными commit'ами для интеграционных тестов.
    Используется когда нужно тестировать реальные транзакции.
    """
    session = test_session_factory()

    # Создаем дефолтное сообщество для интеграционных тестов
    from orm.community import Community
    from auth.orm import Author
    import time

    # Создаем системного автора если его нет
    system_author = session.query(Author).filter(Author.slug == "system").first()
    if not system_author:
        system_author = Author(
            name="System",
            slug="system",
            email="system@test.local",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            last_seen=int(time.time())
        )
        session.add(system_author)
        session.flush()

    # Создаем дефолтное сообщество если его нет
    default_community = session.query(Community).filter(Community.id == 1).first()
    if not default_community:
        default_community = Community(
            id=1,
            name="Главное сообщество",
            slug="main",
            desc="Основное сообщество для тестов",
            pic="",
            created_at=int(time.time()),
            created_by=system_author.id,
            settings={"default_roles": ["reader", "author"], "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"]},
            private=False
        )
        session.add(default_community)
        session.commit()

    yield session

    # Очищаем все данные после теста
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


@pytest.fixture(scope="session")
def test_app():
    """Create a test client and session factory."""
    client, session_local = get_test_client()
    return client, session_local


@pytest.fixture
def test_client(test_app):
    """Get the test client."""
    client, _ = test_app
    return client


@pytest.fixture
async def redis_client():
    """Create a test Redis client."""
    try:
        await redis.connect()
        await redis.execute("FLUSHALL")  # Очищаем Redis перед каждым тестом
        yield redis
        await redis.execute("FLUSHALL")  # Очищаем после теста
    finally:
        try:
            await redis.disconnect()
        except Exception:
            pass


@pytest.fixture
def oauth_db_session(test_session_factory):
    """
    Fixture для dependency injection OAuth модуля с тестовой БД.
    Настраивает OAuth модуль на использование тестовой сессии.
    """
    # Импортируем OAuth модуль и настраиваем dependency injection
    from auth import oauth

    # Сохраняем оригинальную фабрику через SessionManager
    original_factory = oauth.session_manager._factory

    # Устанавливаем тестовую фабрику
    oauth.set_session_factory(lambda: test_session_factory())

    session = test_session_factory()

    # Создаем дефолтное сообщество для OAuth тестов
    from orm.community import Community
    from auth.orm import Author
    import time

    # Создаем системного автора если его нет
    system_author = session.query(Author).filter(Author.slug == "system").first()
    if not system_author:
        system_author = Author(
            name="System",
            slug="system",
            email="system@test.local",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            last_seen=int(time.time())
        )
        session.add(system_author)
        session.flush()

    # Создаем дефолтное сообщество если его нет
    default_community = session.query(Community).filter(Community.id == 1).first()
    if not default_community:
        default_community = Community(
            id=1,
            name="Главное сообщество",
            slug="main",
            desc="Основное сообщество для OAuth тестов",
            pic="",
            created_at=int(time.time()),
            created_by=system_author.id,
            settings={"default_roles": ["reader", "author"], "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"]},
            private=False
        )
        session.add(default_community)
        session.commit()

    yield session

    # Очищаем данные и восстанавливаем оригинальную фабрику
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
        oauth.session_manager.set_factory(original_factory)
