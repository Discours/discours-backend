"""
Тесты для системы ролей в сообществах с учетом наследования ролей.

Проверяет работу с ролями пользователей в сообществах,
включая наследование разрешений между ролями.
"""

import pytest
import time
import uuid
from unittest.mock import patch, MagicMock

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.rbac import (
    initialize_community_permissions,
    get_permissions_for_role,
    user_has_permission,
    roles_have_permission
)
from services.db import local_session


@pytest.fixture
def unique_email():
    """Генерирует уникальный email для каждого теста"""
    return f"test-{uuid.uuid4()}@example.com"


@pytest.fixture
def unique_slug():
    """Генерирует уникальный slug для каждого теста"""
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def session():
    """Создает сессию базы данных для тестов"""
    with local_session() as session:
        yield session
        session.rollback()


class TestCommunityRoleInheritance:
    """Тесты наследования ролей в сообществах"""

    @pytest.mark.asyncio
    async def test_community_author_role_inheritance(self, session, unique_email, unique_slug):
        """Тест наследования ролей в CommunityAuthor"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test User",
            slug=unique_slug,
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Community",
            slug=f"test-community-{unique_slug}",
            desc="Test community for role inheritance",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        # Инициализируем разрешения для сообщества
        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью author
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="author"
        )
        session.add(ca)
        session.commit()

        # Проверяем что author наследует разрешения reader
        reader_permissions = ["shout:read", "topic:read", "collection:read", "chat:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Author должен наследовать разрешение {perm} от reader"

        # Проверяем специфичные разрешения author
        author_permissions = ["draft:create", "shout:create", "collection:create", "invite:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Author должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_community_editor_role_inheritance(self, session, unique_email, unique_slug):
        """Тест наследования ролей для editor в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Editor",
            slug=f"test-editor-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Editor Community",
            slug=f"test-editor-community-{unique_slug}",
            desc="Test community for editor role",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью editor
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="editor"
        )
        session.add(ca)
        session.commit()

        # Проверяем что editor наследует разрешения author
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Editor должен наследовать разрешение {perm} от author"

        # Проверяем что editor наследует разрешения reader через author
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Editor должен наследовать разрешение {perm} от reader через author"

        # Проверяем специфичные разрешения editor
        editor_permissions = ["shout:delete_any", "shout:update_any", "topic:create", "community:create"]
        for perm in editor_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Editor должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_community_admin_role_inheritance(self, session, unique_email, unique_slug):
        """Тест наследования ролей для admin в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Admin",
            slug=f"test-admin-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Admin Community",
            slug=f"test-admin-community-{unique_slug}",
            desc="Test community for admin role",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью admin
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="admin"
        )
        session.add(ca)
        session.commit()

        # Проверяем что admin имеет разрешения всех ролей через наследование
        all_role_permissions = [
            "shout:read",        # reader
            "draft:create",      # author
            "shout:delete_any",  # editor
            "author:delete_any"  # admin
        ]

        for perm in all_role_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Admin должен иметь разрешение {perm} через наследование"

    @pytest.mark.asyncio
    async def test_community_expert_role_inheritance(self, session, unique_email, unique_slug):
        """Тест наследования ролей для expert в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Expert",
            slug=f"test-expert-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Expert Community",
            slug=f"test-expert-community-{unique_slug}",
            desc="Test community for expert role",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью expert
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="expert"
        )
        session.add(ca)
        session.commit()

        # Проверяем что expert наследует разрешения reader
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Expert должен наследовать разрешение {perm} от reader"

        # Проверяем специфичные разрешения expert
        expert_permissions = ["reaction:create:PROOF", "reaction:create:DISPROOF", "reaction:create:AGREE"]
        for perm in expert_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Expert должен иметь разрешение {perm}"

        # Проверяем что expert НЕ имеет разрешения author
        author_permissions = ["draft:create", "shout:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert not has_permission, f"Expert НЕ должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_community_artist_role_inheritance(self, session, unique_email, unique_slug):
        """Тест наследования ролей для artist в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Artist",
            slug=f"test-artist-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Artist Community",
            slug=f"test-artist-community-{unique_slug}",
            desc="Test community for artist role",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью artist
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="artist"
        )
        session.add(ca)
        session.commit()

        # Проверяем что artist наследует разрешения author
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Artist должен наследовать разрешение {perm} от author"

        # Проверяем что artist наследует разрешения reader через author
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Artist должен наследовать разрешение {perm} от reader через author"

        # Проверяем специфичные разрешения artist
        artist_permissions = ["reaction:create:CREDIT", "reaction:read:CREDIT", "reaction:update_own:CREDIT"]
        for perm in artist_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Artist должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_community_multiple_roles_inheritance(self, session, unique_email, unique_slug):
        """Тест множественных ролей с наследованием в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Multi-Role User",
            slug=f"test-multi-role-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Multi-Role Community",
            slug=f"test-multi-role-community-{unique_slug}",
            desc="Test community for multiple roles",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с несколькими ролями
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="author,expert"
        )
        session.add(ca)
        session.commit()

        # Проверяем разрешения от роли author
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Пользователь с ролями author,expert должен иметь разрешение {perm} от author"

        # Проверяем разрешения от роли expert
        expert_permissions = ["reaction:create:PROOF", "reaction:create:DISPROOF", "reaction:create:AGREE"]
        for perm in expert_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Пользователь с ролями author,expert должен иметь разрешение {perm} от expert"

        # Проверяем общие разрешения от reader (наследуются обеими ролями)
        reader_permissions = ["shout:read", "topic:read", "collection:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Пользователь с ролями author,expert должен иметь разрешение {perm} от reader"

    @pytest.mark.asyncio
    async def test_community_roles_have_permission_inheritance(self, session, unique_email, unique_slug):
        """Тест функции roles_have_permission с наследованием в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Permission Check",
            slug=f"test-permission-check-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Permission Community",
            slug=f"test-permission-community-{unique_slug}",
            desc="Test community for permission checks",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Проверяем что editor имеет разрешения author через наследование
        has_author_permission = await roles_have_permission(["editor"], "draft:create", community.id)
        assert has_author_permission, "Editor должен иметь разрешение draft:create через наследование от author"

        # Проверяем что admin имеет разрешения reader через наследование
        has_reader_permission = await roles_have_permission(["admin"], "shout:read", community.id)
        assert has_reader_permission, "Admin должен иметь разрешение shout:read через наследование от reader"

        # Проверяем что artist имеет разрешения author через наследование
        has_artist_author_permission = await roles_have_permission(["artist"], "shout:create", community.id)
        assert has_artist_author_permission, "Artist должен иметь разрешение shout:create через наследование от author"

        # Проверяем что expert НЕ имеет разрешения author
        has_expert_author_permission = await roles_have_permission(["expert"], "draft:create", community.id)
        assert not has_expert_author_permission, "Expert НЕ должен иметь разрешение draft:create"

    @pytest.mark.asyncio
    async def test_community_deep_inheritance_chain(self, session, unique_email, unique_slug):
        """Тест глубокой цепочки наследования в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Deep Inheritance",
            slug=f"test-deep-inheritance-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Deep Inheritance Community",
            slug=f"test-deep-inheritance-community-{unique_slug}",
            desc="Test community for deep inheritance",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью admin
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="admin"
        )
        session.add(ca)
        session.commit()

        # Проверяем что admin имеет разрешения через всю цепочку наследования
        # admin -> editor -> author -> reader
        inheritance_chain_permissions = [
            "shout:read",        # reader
            "draft:create",      # author
            "shout:delete_any",  # editor
            "author:delete_any"  # admin
        ]

        for perm in inheritance_chain_permissions:
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert has_permission, f"Admin должен иметь разрешение {perm} через цепочку наследования"

    @pytest.mark.asyncio
    async def test_community_permission_denial_with_inheritance(self, session, unique_email, unique_slug):
        """Тест отказа в разрешениях с учетом наследования в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Permission Denial",
            slug=f"test-permission-denial-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Permission Denial Community",
            slug=f"test-permission-denial-community-{unique_slug}",
            desc="Test community for permission denial",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Создаем CommunityAuthor с ролью reader
        ca = CommunityAuthor(
            community_id=community.id,
            author_id=user.id,
            roles="reader"
        )
        session.add(ca)
        session.commit()

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
            has_permission = await user_has_permission(user.id, perm, community.id)
            assert not has_permission, f"Reader НЕ должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_community_role_permissions_consistency(self, session, unique_email, unique_slug):
        """Тест консистентности разрешений ролей в сообществе"""
        # Создаем тестового пользователя
        user = Author(
            email=unique_email,
            name="Test Consistency",
            slug=f"test-consistency-{unique_slug}",
            created_at=int(time.time())
        )
        user.set_password("password123")
        session.add(user)
        session.flush()

        # Создаем тестовое сообщество
        community = Community(
            name="Test Consistency Community",
            slug=f"test-consistency-community-{unique_slug}",
            desc="Test community for role consistency",
            created_by=user.id,
            created_at=int(time.time())
        )
        session.add(community)
        session.flush()

        await initialize_community_permissions(community.id)

        # Проверяем что все роли имеют корректные разрешения
        role_permissions_map = {
            "reader": ["shout:read", "topic:read", "collection:read"],
            "author": ["draft:create", "shout:create", "collection:create"],
            "expert": ["reaction:create:PROOF", "reaction:create:DISPROOF"],
            "artist": ["reaction:create:CREDIT", "reaction:read:CREDIT"],
            "editor": ["shout:delete_any", "shout:update_any", "topic:create"],
            "admin": ["author:delete_any", "author:update_any"]
        }

        for role, expected_permissions in role_permissions_map.items():
            # Создаем CommunityAuthor с текущей ролью
            ca = CommunityAuthor(
                community_id=community.id,
                author_id=user.id,
                roles=role
            )
            session.add(ca)
            session.commit()

            # Проверяем что роль имеет ожидаемые разрешения
            for perm in expected_permissions:
                has_permission = await user_has_permission(user.id, perm, community.id)
                assert has_permission, f"Роль {role} должна иметь разрешение {perm}"

            # Удаляем запись для следующей итерации
            session.delete(ca)
            session.commit()
