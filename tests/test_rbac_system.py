"""
Тесты для системы RBAC (Role-Based Access Control).

Проверяет работу с ролями, разрешениями и наследованием ролей.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.rbac import (
    initialize_community_permissions,
    get_role_permissions_for_community,
    get_permissions_for_role,
    user_has_permission,
    roles_have_permission
)
from services.db import local_session


@pytest.fixture
def test_users(db_session):
    """Создает тестовых пользователей"""
    users = []

    # Создаем пользователей с ID 1-5
    for i in range(1, 6):
        user = db_session.query(Author).where(Author.id == i).first()
        if not user:
            user = Author(id=i, email=f"user{i}@example.com", name=f"Test User {i}", slug=f"test-user-{i}")
            user.set_password("password123")
            db_session.add(user)
        users.append(user)

    db_session.commit()
    return users


@pytest.fixture
def test_community(db_session, test_users):
    """Создает тестовое сообщество"""
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


class TestRBACRoleInheritance:
    """Тесты для проверки наследования ролей"""

    @pytest.mark.asyncio
    async def test_role_inheritance_author_inherits_reader(self, db_session, test_community):
        """Тест что роль author наследует разрешения от reader"""
        # Инициализируем разрешения для сообщества
        await initialize_community_permissions(test_community.id)

        # Получаем разрешения для роли author
        author_permissions = await get_permissions_for_role("author", test_community.id)
        reader_permissions = await get_permissions_for_role("reader", test_community.id)

        # Проверяем что author имеет все разрешения reader
        for perm in reader_permissions:
            assert perm in author_permissions, f"Author должен наследовать разрешение {perm} от reader"

        # Проверяем что author имеет дополнительные разрешения
        author_specific = ["draft:read", "draft:create", "shout:create", "shout:update"]
        for perm in author_specific:
            assert perm in author_permissions, f"Author должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_role_inheritance_editor_inherits_author(self, db_session, test_community):
        """Тест что роль editor наследует разрешения от author"""
        await initialize_community_permissions(test_community.id)

        editor_permissions = await get_permissions_for_role("editor", test_community.id)
        author_permissions = await get_permissions_for_role("author", test_community.id)

        # Проверяем что editor имеет все разрешения author
        for perm in author_permissions:
            assert perm in editor_permissions, f"Editor должен наследовать разрешение {perm} от author"

        # Проверяем что editor имеет дополнительные разрешения
        editor_specific = ["shout:delete_any", "shout:update_any", "topic:create", "community:create"]
        for perm in editor_specific:
            assert perm in editor_permissions, f"Editor должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_role_inheritance_admin_inherits_editor(self, db_session, test_community):
        """Тест что роль admin наследует разрешения от editor"""
        await initialize_community_permissions(test_community.id)

        admin_permissions = await get_permissions_for_role("admin", test_community.id)
        editor_permissions = await get_permissions_for_role("editor", test_community.id)

        # Проверяем что admin имеет все разрешения editor
        for perm in editor_permissions:
            assert perm in admin_permissions, f"Admin должен наследовать разрешение {perm} от editor"

        # Проверяем что admin имеет дополнительные разрешения
        admin_specific = ["author:delete_any", "author:update_any", "chat:delete_any", "message:delete_any"]
        for perm in admin_specific:
            assert perm in admin_permissions, f"Admin должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_role_inheritance_expert_inherits_reader(self, db_session, test_community):
        """Тест что роль expert наследует разрешения от reader"""
        await initialize_community_permissions(test_community.id)

        expert_permissions = await get_permissions_for_role("expert", test_community.id)
        reader_permissions = await get_permissions_for_role("reader", test_community.id)

        # Проверяем что expert имеет все разрешения reader
        for perm in reader_permissions:
            assert perm in expert_permissions, f"Expert должен наследовать разрешение {perm} от reader"

        # Проверяем что expert имеет дополнительные разрешения
        expert_specific = ["reaction:create:PROOF", "reaction:create:DISPROOF", "reaction:create:AGREE"]
        for perm in expert_specific:
            assert perm in expert_permissions, f"Expert должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_role_inheritance_artist_inherits_author(self, db_session, test_community):
        """Тест что роль artist наследует разрешения от author"""
        await initialize_community_permissions(test_community.id)

        artist_permissions = await get_permissions_for_role("artist", test_community.id)
        author_permissions = await get_permissions_for_role("author", test_community.id)

        # Проверяем что artist имеет все разрешения author
        for perm in author_permissions:
            assert perm in artist_permissions, f"Artist должен наследовать разрешение {perm} от author"

        # Проверяем что artist имеет дополнительные разрешения
        artist_specific = ["reaction:create:CREDIT", "reaction:read:CREDIT", "reaction:update:CREDIT"]
        for perm in artist_specific:
            assert perm in artist_permissions, f"Artist должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_role_inheritance_deep_inheritance(self, db_session, test_community):
        """Тест глубокого наследования: admin -> editor -> author -> reader"""
        await initialize_community_permissions(test_community.id)

        admin_permissions = await get_permissions_for_role("admin", test_community.id)
        reader_permissions = await get_permissions_for_role("reader", test_community.id)

        # Проверяем что admin имеет все разрешения reader через цепочку наследования
        for perm in reader_permissions:
            assert perm in admin_permissions, f"Admin должен наследовать разрешение {perm} через цепочку наследования"

    @pytest.mark.asyncio
    async def test_role_inheritance_no_circular_dependency(self, db_session, test_community):
        """Тест что нет циклических зависимостей в наследовании ролей"""
        await initialize_community_permissions(test_community.id)

        # Получаем все роли и проверяем что они корректно обрабатываются
        all_roles = ["reader", "author", "artist", "expert", "editor", "admin"]

        for role in all_roles:
            permissions = await get_permissions_for_role(role, test_community.id)
            # Проверяем что список разрешений не пустой и не содержит циклических ссылок
            assert len(permissions) > 0, f"Роль {role} должна иметь разрешения"
            assert role not in permissions, f"Роль {role} не должна ссылаться на саму себя"


class TestRBACPermissionChecking:
    """Тесты для проверки разрешений с учетом наследования"""

    @pytest.mark.asyncio
    async def test_user_with_author_role_has_reader_permissions(self, db_session, test_users, test_community):
        """Тест что пользователь с ролью author имеет разрешения reader"""
        # Используем local_session для создания записи
        from services.db import local_session
        from orm.community import CommunityAuthor

        with local_session() as session:
            # Удаляем существующую запись если есть
            existing_ca = session.query(CommunityAuthor).where(
                CommunityAuthor.community_id == test_community.id,
                CommunityAuthor.author_id == test_users[0].id
            ).first()
            if existing_ca:
                session.delete(existing_ca)
                session.commit()

            # Создаем новую запись
            ca = CommunityAuthor(
                community_id=test_community.id,
                author_id=test_users[0].id,
                roles="author"
            )
            session.add(ca)
            session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что пользователь имеет разрешения reader
        reader_permissions = ["shout:read", "topic:read", "collection:read", "chat:read"]
        for perm in reader_permissions:
            has_permission = await user_has_permission(test_users[0].id, perm, test_community.id)
            assert has_permission, f"Пользователь с ролью author должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_user_with_editor_role_has_author_permissions(self, db_session, test_users, test_community):
        """Тест что пользователь с ролью editor имеет разрешения author"""
        # Используем local_session для создания записи
        from services.db import local_session
        from orm.community import CommunityAuthor

        with local_session() as session:
            # Удаляем существующую запись если есть
            existing_ca = session.query(CommunityAuthor).where(
                CommunityAuthor.community_id == test_community.id,
                CommunityAuthor.author_id == test_users[0].id
            ).first()
            if existing_ca:
                session.delete(existing_ca)
                session.commit()

            # Создаем новую запись
            ca = CommunityAuthor(
                community_id=test_community.id,
                author_id=test_users[0].id,
                roles="editor"
            )
            session.add(ca)
            session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем что пользователь имеет разрешения author
        author_permissions = ["draft:create", "shout:create", "collection:create"]
        for perm in author_permissions:
            has_permission = await user_has_permission(test_users[0].id, perm, test_community.id)
            assert has_permission, f"Пользователь с ролью editor должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_user_with_admin_role_has_all_permissions(self, db_session, test_users, test_community):
        """Тест что пользователь с ролью admin имеет все разрешения"""
        # Используем local_session для создания записи
        from services.db import local_session
        from orm.community import CommunityAuthor

        with local_session() as session:
            # Удаляем существующую запись если есть
            existing_ca = session.query(CommunityAuthor).where(
                CommunityAuthor.community_id == test_community.id,
                CommunityAuthor.author_id == test_users[0].id
            ).first()
            if existing_ca:
                session.delete(existing_ca)
                session.commit()

            # Создаем новую запись
            ca = CommunityAuthor(
                community_id=test_community.id,
                author_id=test_users[0].id,
                roles="admin"
            )
            session.add(ca)
            session.commit()

        await initialize_community_permissions(test_community.id)

        # Проверяем разрешения разных уровней
        all_permissions = [
            "shout:read",        # reader
            "draft:create",      # author
            "shout:delete_any",  # editor
            "author:delete_any"  # admin
        ]

        for perm in all_permissions:
            has_permission = await user_has_permission(test_users[0].id, perm, test_community.id)
            assert has_permission, f"Пользователь с ролью admin должен иметь разрешение {perm}"

    @pytest.mark.asyncio
    async def test_roles_have_permission_with_inheritance(self, db_session, test_community):
        """Тест функции roles_have_permission с учетом наследования"""
        await initialize_community_permissions(test_community.id)

        # Проверяем что editor имеет разрешения author
        has_author_permission = await roles_have_permission(["editor"], "draft:create", test_community.id)
        assert has_author_permission, "Editor должен иметь разрешение draft:create через наследование от author"

        # Проверяем что admin имеет разрешения reader
        has_reader_permission = await roles_have_permission(["admin"], "shout:read", test_community.id)
        assert has_reader_permission, "Admin должен иметь разрешение shout:read через наследование от reader"


class TestRBACInitialization:
    """Тесты для инициализации системы RBAC"""

    @pytest.mark.asyncio
    async def test_initialize_community_permissions(self, db_session, test_community):
        """Тест инициализации разрешений для сообщества"""
        await initialize_community_permissions(test_community.id)

        # Проверяем что разрешения инициализированы
        permissions = await get_role_permissions_for_community(test_community.id)
        assert permissions is not None
        assert len(permissions) > 0

        # Проверяем что все роли присутствуют
        expected_roles = ["reader", "author", "artist", "expert", "editor", "admin"]
        for role in expected_roles:
            assert role in permissions, f"Роль {role} должна быть в инициализированных разрешениях"

    @pytest.mark.asyncio
    async def test_get_role_permissions_for_community_auto_init(self, db_session, test_community):
        """Тест автоматической инициализации при получении разрешений"""
        # Получаем разрешения без предварительной инициализации
        permissions = await get_role_permissions_for_community(test_community.id)

        assert permissions is not None
        assert len(permissions) > 0

        # Проверяем что все роли присутствуют
        expected_roles = ["reader", "author", "artist", "expert", "editor", "admin"]
        for role in expected_roles:
            assert role in permissions, f"Роль {role} должна быть в разрешениях"
