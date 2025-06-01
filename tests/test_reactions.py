from datetime import datetime

import pytest

from auth.orm import Author, AuthorRole, Role
from orm.reaction import ReactionKind
from orm.shout import Shout
from resolvers.reaction import create_reaction


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
