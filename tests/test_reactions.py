from datetime import datetime

import pytest

from auth.orm import Author
from orm.community import CommunityAuthor
from orm.reaction import ReactionKind
from orm.shout import Shout
from resolvers.reaction import create_reaction


def ensure_test_user_with_roles(db_session):
    """Создает тестового пользователя с ID 1 и назначает ему роли через CSV"""
    # Создаем пользователя с ID 1 если его нет
    test_user = db_session.query(Author).where(Author.id == 1).first()
    if not test_user:
        test_user = Author(id=1, email="test@example.com", name="Test User", slug="test-user")
        test_user.set_password("password123")
        db_session.add(test_user)
        db_session.flush()

    # Создаем связь пользователя с сообществом с ролями через CSV
    community_author = (
        db_session.query(CommunityAuthor)
        .where(CommunityAuthor.community_id == 1, CommunityAuthor.author_id == 1)
        .first()
    )

    if not community_author:
        community_author = CommunityAuthor(
            community_id=1,
            author_id=1,
            roles="reader,author",  # Роли через CSV
            joined_at=int(datetime.now().timestamp()),
        )
        db_session.add(community_author)
    else:
        # Обновляем роли если связь уже существует
        community_author.roles = "reader,author"

    db_session.commit()
    return test_user


class MockInfo:
    """Мок для GraphQL info объекта"""

    def __init__(self, author_id: int):
        self.context = {
            "request": None,  # Тестовый режим
            "author": {"id": author_id, "name": "Test User"},
            "roles": ["reader", "author"],
            "is_admin": False,
        }


@pytest.fixture
def test_setup(db_session):
    """Set up test data."""
    now = int(datetime.now().timestamp())
    author = ensure_test_user_with_roles(db_session)

    shout = Shout(
        title="Test Shout",
        slug="test-shout-reactions",
        created_by=author.id,
        body="This is a test shout",
        layout="article",
        lang="ru",
        community=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(shout)
    db_session.commit()
    return {"author": author, "shout": shout}


@pytest.mark.asyncio
async def test_create_reaction(db_session, test_setup):
    """Test creating a reaction on a shout using direct resolver call."""
    # Создаем мок info
    info = MockInfo(test_setup["author"].id)

    # Вызываем резолвер напрямую
    result = await create_reaction(
        None,
        info,
        reaction={
            "shout": test_setup["shout"].id,
            "kind": ReactionKind.LIKE.value,
            "body": "Great post!",
        },
    )

    # Проверяем результат - резолвер должен работать без падения
    assert result is not None
    assert isinstance(result, dict)  # Должен вернуть словарь
