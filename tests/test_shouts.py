from datetime import datetime

import pytest

from auth.orm import Author
from orm.community import CommunityAuthor
from orm.shout import Shout
from resolvers.reader import get_shout



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
    author = Author(id=1, email="test@example.com", name="Test User", slug="test-user")
    author.set_password("password123")
    author.set_email_verified(True)
    ca = CommunityAuthor(community_id=1, author_id=author.id, roles="reader,author")
    db_session.add(author)
    db_session.add(ca)
    db_session.commit()
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
