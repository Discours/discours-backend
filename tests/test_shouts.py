from datetime import datetime

import pytest

from auth.orm import Author, AuthorRole, Role
from orm.shout import Shout
from resolvers.reader import get_shout


def ensure_test_user_with_roles(db_session):
    """Создает тестового пользователя с ID 1 и назначает ему роли"""
    # Создаем роли если их нет
    reader_role = db_session.query(Role).filter(Role.id == "reader").first()
    if not reader_role:
        reader_role = Role(id="reader", name="Читатель")
        db_session.add(reader_role)

    author_role = db_session.query(Role).filter(Role.id == "author").first()
    if not author_role:
        author_role = Role(id="author", name="Автор")
        db_session.add(author_role)

    # Создаем пользователя с ID 1 если его нет
    test_user = db_session.query(Author).filter(Author.id == 1).first()
    if not test_user:
        test_user = Author(id=1, email="test@example.com", name="Test User", slug="test-user")
        test_user.set_password("password123")
        db_session.add(test_user)
        db_session.flush()

    # Удаляем старые роли и добавляем новые
    db_session.query(AuthorRole).filter(AuthorRole.author == 1).delete()

    # Добавляем роли
    for role_id in ["reader", "author"]:
        author_role_link = AuthorRole(community=1, author=1, role=role_id)
        db_session.add(author_role_link)

    db_session.commit()
    return test_user


class MockInfo:
    """Мок для GraphQL info объекта"""

    def __init__(self, author_id: int = None, requested_fields: list[str] = None):
        self.context = {
            "request": None,  # Тестовый режим
            "author": {"id": author_id, "name": "Test User"} if author_id else None,
            "roles": ["reader", "author"] if author_id else [],
            "is_admin": False,
        }
        # Добавляем field_nodes для совместимости с резолверами
        self.field_nodes = [MockFieldNode(requested_fields or [])]


class MockFieldNode:
    """Мок для GraphQL field node"""

    def __init__(self, requested_fields: list[str]):
        self.selection_set = MockSelectionSet(requested_fields)


class MockSelectionSet:
    """Мок для GraphQL selection set"""

    def __init__(self, requested_fields: list[str]):
        self.selections = [MockSelection(field) for field in requested_fields]


class MockSelection:
    """Мок для GraphQL selection"""

    def __init__(self, field_name: str):
        self.name = MockName(field_name)


class MockName:
    """Мок для GraphQL name"""

    def __init__(self, value: str):
        self.value = value


@pytest.fixture
def test_shout(db_session):
    """Create test shout with required fields."""
    author = ensure_test_user_with_roles(db_session)
    now = int(datetime.now().timestamp())

    # Создаем публикацию со всеми обязательными полями
    shout = Shout(
        title="Test Shout",
        body="This is a test shout",
        slug="test-shout-get-unique",
        created_by=author.id,
        layout="article",
        lang="ru",
        community=1,
        created_at=now,
        updated_at=now,
        published_at=now,  # Важно: делаем публикацию опубликованной
    )
    db_session.add(shout)
    db_session.commit()
    return shout


@pytest.mark.asyncio
async def test_get_shout(db_session):
    """Test that get_shout resolver doesn't crash."""
    # Создаем мок info
    info = MockInfo(requested_fields=["id", "title", "body", "slug"])

    # Вызываем резолвер с несуществующим slug - должен вернуть None без ошибок
    result = await get_shout(None, info, slug="nonexistent-slug")

    # Проверяем что резолвер не упал и корректно вернул None
    assert result is None
