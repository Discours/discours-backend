import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import time
import uuid
from starlette.testclient import TestClient

from services.redis import redis
from orm.base import BaseModel as Base


def get_test_client():
    """
    Создает и возвращает тестовый клиент для интеграционных тестов.

    Returns:
        TestClient: Клиент для выполнения тестовых запросов
    """
    from starlette.testclient import TestClient

    # Отложенный импорт для предотвращения циклических зависимостей
    def _import_app():
        from main import app
        return app

    return TestClient(_import_app())


@pytest.fixture(scope="session")
def test_engine():
    """
    Создает тестовый engine для всей сессии тестирования.
    Использует in-memory SQLite для быстрых тестов.
    """
    # Импортируем все модели, чтобы они были зарегистрированы
    from orm.base import BaseModel as Base
    from orm.community import Community, CommunityAuthor
    from auth.orm import Author
    from orm.draft import Draft, DraftAuthor, DraftTopic
    from orm.shout import Shout, ShoutAuthor, ShoutTopic, ShoutReactionsFollower
    from orm.topic import Topic
    from orm.reaction import Reaction
    from orm.invite import Invite
    from orm.notification import Notification

    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    # Принудительно удаляем все таблицы и создаем заново
    Base.metadata.drop_all(engine)
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
def db_session(test_session_factory, test_engine):
    """
    Создает новую сессию БД для каждого теста.
    Простая реализация без вложенных транзакций.
    """
    # Принудительно пересоздаем таблицы для каждого теста
    from orm.base import BaseModel as Base
    from sqlalchemy import inspect

    # Удаляем все таблицы
    Base.metadata.drop_all(test_engine)

    # Создаем таблицы заново
    Base.metadata.create_all(test_engine)

    # Проверяем что таблица draft создана с правильной схемой
    inspector = inspect(test_engine)
    draft_columns = [col['name'] for col in inspector.get_columns('draft')]
    print(f"Draft table columns: {draft_columns}")

    # Убеждаемся что колонка shout существует
    if 'shout' not in draft_columns:
        print("WARNING: Column 'shout' not found in draft table!")

    session = test_session_factory()

    # Создаем дефолтное сообщество для тестов
    from orm.community import Community
    from auth.orm import Author
    import time

    # Создаем системного автора если его нет
    system_author = session.query(Author).where(Author.slug == "system").first()
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
    default_community = session.query(Community).where(Community.id == 1).first()
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

    # Создаем дефолтное сообщество для тестов
    from orm.community import Community
    from auth.orm import Author

    # Создаем системного автора если его нет
    system_author = session.query(Author).where(Author.slug == "system").first()
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
        session.commit()

    # Создаем дефолтное сообщество если его нет
    default_community = session.query(Community).where(Community.id == 1).first()
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
    """Создает тестовое приложение"""
    from main import app
    return app


@pytest.fixture
def test_client(test_app):
    """Создает тестовый клиент"""
    from starlette.testclient import TestClient
    return TestClient(test_app)


@pytest.fixture
async def redis_client():
    """Создает тестовый Redis клиент"""
    from services.redis import redis

    # Очищаем тестовые данные
    await redis.execute("FLUSHDB")

    yield redis

    # Очищаем после тестов
    await redis.execute("FLUSHDB")


@pytest.fixture
def oauth_db_session(test_session_factory):
    """
    Создает сессию БД для OAuth тестов.
    """
    session = test_session_factory()
    yield session
    session.close()


# ============================================================================
# ОБЩИЕ ФИКСТУРЫ ДЛЯ RBAC ТЕСТОВ
# ============================================================================

@pytest.fixture
def unique_email():
    """Генерирует уникальный email для каждого теста"""
    return f"test-{uuid.uuid4()}@example.com"


@pytest.fixture
def test_users(db_session):
    """Создает тестовых пользователей для RBAC тестов"""
    from auth.orm import Author

    users = []

    # Создаем пользователей с ID 1-5
    for i in range(1, 6):
        user = db_session.query(Author).where(Author.id == i).first()
        if not user:
            user = Author(
                id=i,
                email=f"user{i}@example.com",
                name=f"Test User {i}",
                slug=f"test-user-{i}",
                created_at=int(time.time())
            )
            user.set_password("password123")
            db_session.add(user)
        users.append(user)

    db_session.commit()
    return users


@pytest.fixture
def test_community(db_session, test_users):
    """Создает тестовое сообщество для RBAC тестов"""
    from orm.community import Community

    community = db_session.query(Community).where(Community.id == 1).first()
    if not community:
        community = Community(
            id=1,
            name="Test Community",
            slug="test-community",
            desc="Test community for RBAC tests",
            created_by=test_users[0].id,
            created_at=int(time.time())
        )
        db_session.add(community)
        db_session.commit()

    return community


@pytest.fixture
def simple_user(db_session):
    """Создает простого тестового пользователя"""
    from auth.orm import Author
    from orm.community import CommunityAuthor

    # Очищаем любые существующие записи с этим ID/email
    db_session.query(Author).where(
        (Author.id == 200) | (Author.email == "simple_user@example.com")
    ).delete()
    db_session.commit()

    user = Author(
        id=200,
        email="simple_user@example.com",
        name="Simple User",
        slug="simple-user",
        created_at=int(time.time())
    )
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()

    yield user

    # Очистка после теста
    try:
        # Удаляем связанные записи CommunityAuthor
        db_session.query(CommunityAuthor).where(CommunityAuthor.author_id == user.id).delete(synchronize_session=False)
        # Удаляем самого пользователя
        db_session.query(Author).where(Author.id == user.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture
def simple_community(db_session, simple_user):
    """Создает простое тестовое сообщество"""
    from orm.community import Community, CommunityAuthor

    # Очищаем любые существующие записи с этим ID/slug
    db_session.query(Community).where(Community.slug == "simple-test-community").delete()
    db_session.commit()

    community = Community(
        name="Simple Test Community",
        slug="simple-test-community",
        desc="Simple community for tests",
        created_by=simple_user.id,
        created_at=int(time.time()),
        settings={
            "default_roles": ["reader", "author"],
            "available_roles": ["reader", "author", "editor"]
        }
    )
    db_session.add(community)
    db_session.commit()

    yield community

    # Очистка после теста
    try:
        # Удаляем связанные записи CommunityAuthor
        db_session.query(CommunityAuthor).where(CommunityAuthor.community_id == community.id).delete()
        # Удаляем само сообщество
        db_session.query(Community).where(Community.id == community.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture
def community_without_creator(db_session):
    """Создает сообщество без создателя (created_by = None)"""
    from orm.community import Community

    community = Community(
        id=100,
        name="Community Without Creator",
        slug="community-without-creator",
        desc="Test community without creator",
        created_by=None,  # Ключевое изменение - создатель отсутствует
        created_at=int(time.time())
    )
    db_session.add(community)
    db_session.commit()
    return community


@pytest.fixture
def admin_user_with_roles(db_session, test_users, test_community):
    """Создает пользователя с ролями администратора"""
    from orm.community import CommunityAuthor

    user = test_users[0]

    # Создаем CommunityAuthor с ролями администратора
    ca = CommunityAuthor(
        community_id=test_community.id,
        author_id=user.id,
        roles="admin,editor,author"
    )
    db_session.add(ca)
    db_session.commit()

    return user


@pytest.fixture
def regular_user_with_roles(db_session, test_users, test_community):
    """Создает обычного пользователя с ролями"""
    from orm.community import CommunityAuthor

    user = test_users[1]

    # Создаем CommunityAuthor с обычными ролями
    ca = CommunityAuthor(
        community_id=test_community.id,
        author_id=user.id,
        roles="reader,author"
    )
    db_session.add(ca)
    db_session.commit()

    return user


# ============================================================================
# УТИЛИТЫ ДЛЯ ТЕСТОВ
# ============================================================================

def create_test_user(db_session, user_id, email, name, slug, roles=None):
    """Утилита для создания тестового пользователя с ролями"""
    from auth.orm import Author
    from orm.community import CommunityAuthor

    # Создаем пользователя
    user = Author(
        id=user_id,
        email=email,
        name=name,
        slug=slug,
        created_at=int(time.time())
    )
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()

    # Добавляем роли если указаны
    if roles:
        ca = CommunityAuthor(
            community_id=1,  # Используем основное сообщество
            author_id=user.id,
            roles=",".join(roles)
        )
        db_session.add(ca)
        db_session.commit()

    return user


def create_test_community(db_session, community_id, name, slug, created_by=None, settings=None):
    """Утилита для создания тестового сообщества"""
    from orm.community import Community

    community = Community(
        id=community_id,
        name=name,
        slug=slug,
        desc=f"Test community {name}",
        created_by=created_by,
        created_at=int(time.time()),
        settings=settings or {"default_roles": ["reader"], "available_roles": ["reader", "author", "editor", "admin"]}
    )
    db_session.add(community)
    db_session.commit()

    return community


def cleanup_test_data(db_session, user_ids=None, community_ids=None):
    """Утилита для очистки тестовых данных"""
    from orm.community import CommunityAuthor

    # Очищаем CommunityAuthor записи
    if user_ids:
        db_session.query(CommunityAuthor).where(CommunityAuthor.author_id.in_(user_ids)).delete(synchronize_session=False)

    if community_ids:
        db_session.query(CommunityAuthor).where(CommunityAuthor.community_id.in_(community_ids)).delete(synchronize_session=False)

    db_session.commit()
