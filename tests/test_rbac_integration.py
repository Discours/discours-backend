"""
Интеграционные тесты для системы RBAC.

Проверяет работу системы ролей и разрешений в реальных сценариях
с учетом наследования ролей.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import json

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.rbac import (
    initialize_community_permissions,
    get_permissions_for_role,
    user_has_permission,
    roles_have_permission
)
from services.db import local_session
from services.redis import redis


@pytest.fixture
def simple_user(db_session):
    """Создает простого тестового пользователя"""
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
    except Exception as e:
        print(f"Ошибка при очистке тестового пользователя: {e}")


@pytest.fixture
def test_community(db_session, simple_user):
    """Создает тестовое сообщество"""
    # Очищаем существующие записи
    db_session.query(Community).where(Community.id == 999).delete()
    db_session.commit()

    community = Community(
        id=999,
        name="Integration Test Community",
        slug="integration-test-community",
        desc="Community for integration RBAC tests",
        created_by=simple_user.id,
        created_at=int(time.time())
    )
    db_session.add(community)
    db_session.commit()

    yield community

    # Очистка после теста
    try:
        db_session.query(Community).where(Community.id == community.id).delete()
        db_session.commit()
    except Exception as e:
        print(f"Ошибка при очистке тестового сообщества: {e}")


@pytest.fixture(autouse=True)
async def setup_redis():
    """Настройка Redis для каждого теста"""
    # Подключаемся к Redis
    await redis.connect()

    yield

    # Очищаем данные тестового сообщества из Redis
    try:
        await redis.delete("community:roles:999")
    except Exception:
        pass

    # Отключаемся от Redis
    try:
        await redis.disconnect()
    except Exception:
        pass


class TestRBACIntegrationWithInheritance:
    """Интеграционные тесты с учетом наследования ролей"""

    @pytest.mark.asyncio
    async def test_author_role_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест наследования ролей для author"""
        # Создаем запись CommunityAuthor с ролью author
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="author"
        )
        db_session.add(ca)
        db_session.commit()

        # Инициализируем разрешения для сообщества
        await initialize_community_permissions(test_community.id)

        # Проверяем что author имеет разрешения reader через наследование
        reader_permissions = ["shout:read", "topic:read", "collection:read", "chat:read", "message:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Author должен наследовать разрешение {perm} от reader"

        # Проверяем специфичные разрешения author
        author_permissions = ["draft:create", "shout:create", "collection:create", "invite:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Author должен иметь разрешение {perm}"

        # Проверяем что author НЕ имеет разрешения более высоких ролей
        higher_permissions = ["shout:delete_any", "author:delete_any", "community:create"]
        for perm in higher_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert not has_permission, f"Author НЕ должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_editor_role_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест наследования ролей для editor"""
        # Создаем запись CommunityAuthor с ролью editor
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="editor"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что editor имеет разрешения reader через наследование
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Editor должен наследовать разрешение {perm} от reader"

        # Проверяем что editor имеет разрешения author через наследование
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Editor должен наследовать разрешение {perm} от author"

        # Проверяем специфичные разрешения editor
        editor_permissions = ["shout:delete_any", "shout:update_any", "topic:create", "community:create"]
        for perm in editor_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Editor должен иметь разрешение {perm}"

        # Проверяем что editor НЕ имеет разрешения admin
        admin_permissions = ["author:delete_any", "author:update_any"]
        for perm in admin_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert not has_permission, f"Editor НЕ должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_admin_role_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест наследования ролей для admin"""
        # Создаем запись CommunityAuthor с ролью admin
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="admin"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что admin имеет разрешения всех ролей через наследование
        all_role_permissions = [
            "shout:read",        # reader
            "draft:create",      # author
            "shout:delete_any",  # editor
            "author:delete_any"  # admin
        ]

        for perm in all_role_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Admin должен иметь разрешение {perm} через наследование"

    @pytest.mark.asyncio
    async def test_expert_role_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест наследования ролей для expert"""
        # Создаем запись CommunityAuthor с ролью expert
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="expert"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что expert имеет разрешения reader через наследование
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Expert должен наследовать разрешение {perm} от reader"

        # Проверяем специфичные разрешения expert
        expert_permissions = ["reaction:create:PROOF", "reaction:create:DISPROOF", "reaction:create:AGREE"]
        for perm in expert_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Expert должен иметь разрешение {perm}"

        # Проверяем что expert НЕ имеет разрешения author
        author_permissions = ["draft:create", "shout:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert not has_permission, f"Expert НЕ должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_artist_role_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест наследования ролей для artist"""
        # Создаем запись CommunityAuthor с ролью artist
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="artist"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что artist имеет разрешения author через наследование
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Artist должен наследовать разрешение {perm} от author"

        # Проверяем что artist имеет разрешения reader через наследование от author
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Artist должен наследовать разрешение {perm} от reader через author"

        # Проверяем специфичные разрешения artist
        artist_permissions = ["reaction:create:CREDIT", "reaction:read:CREDIT", "reaction:update:CREDIT"]
        for perm in artist_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Artist должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_multiple_roles_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест множественных ролей с наследованием"""
        # Создаем запись CommunityAuthor с несколькими ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="author,expert"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем разрешения от роли author
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Пользователь с ролями author,expert должен иметь разрешение {perm} от author"

        # Проверяем разрешения от роли expert
        expert_permissions = ["reaction:create:PROOF", "reaction:create:DISPROOF", "reaction:create:AGREE"]
        for perm in expert_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Пользователь с ролями author,expert должен иметь разрешение {perm} от expert"

        # Проверяем общие разрешения от reader (наследуются обеими ролями)
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Пользователь с ролями author,expert должен иметь разрешение {perm} от reader"

    @pytest.mark.asyncio
    async def test_roles_have_permission_inheritance_integration(self, db_session, test_community):
        """Интеграционный тест функции roles_have_permission с наследованием"""
        await initialize_community_permissions(test_community.id)

        # Проверяем что editor имеет разрешения author через наследование
        has_author_permission = await roles_have_permission(["editor"], "draft:create", test_community.id)
        assert has_author_permission, "Editor должен иметь разрешение draft:create через наследование от author"

        # Проверяем что admin имеет разрешения reader через наследование
        has_reader_permission = await roles_have_permission(["admin"], "shout:read", test_community.id)
        assert has_reader_permission, "Admin должен иметь разрешение shout:read через наследование от reader"

        # Проверяем что artist имеет разрешения author через наследование
        has_artist_author_permission = await roles_have_permission(["artist"], "shout:create", test_community.id)
        assert has_artist_author_permission, "Artist должен иметь разрешение shout:create через наследование от author"

        # Проверяем что expert НЕ имеет разрешения author
        has_expert_author_permission = await roles_have_permission(["expert"], "draft:create", test_community.id)
        assert not has_expert_author_permission, "Expert НЕ должен иметь разрешение draft:create"

    @pytest.mark.asyncio
    async def test_permission_denial_inheritance_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест отказа в разрешениях с учетом наследования"""
        # Создаем запись CommunityAuthor с ролью reader
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="reader"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что reader НЕ имеет разрешения более высоких ролей
        denied_permissions = [
            "draft:create",      # author
            "shout:create",      # author
            "shout:delete_any",  # editor
            "author:delete_any", # admin
            "reaction:create:PROOF", # expert
            "reaction:create:CREDIT" # artist
        ]

        for perm in denied_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert not has_permission, f"Reader НЕ должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_deep_inheritance_chain_integration(self, db_session, simple_user, test_community):
        """Интеграционный тест глубокой цепочки наследования"""
        # Создаем запись CommunityAuthor с ролью admin
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=simple_user.id,
            roles="admin"
        )
        db_session.add(ca)
        db_session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что admin имеет разрешения через всю цепочку наследования
        # admin -> editor -> author -> reader
        inheritance_chain_permissions = [
            "shout:read",        # reader
            "draft:create",      # author
            "shout:delete_any",  # editor
            "author:delete_any"  # admin
        ]

        for perm in inheritance_chain_permissions:
            has_permission = await user_has_permission(simple_user.id, perm, test_community.id, db_session)
            assert has_permission, f"Admin должен иметь разрешение {perm} через цепочку наследования"
