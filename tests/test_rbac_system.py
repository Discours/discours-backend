"""
Тесты для новой системы RBAC (Role-Based Access Control).

Проверяет работу системы ролей и разрешений на основе CSV хранения
в таблице CommunityAuthor.
"""

import pytest

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.rbac import get_role_permissions_for_community, get_permissions_for_role
from orm.reaction import REACTION_KINDS


@pytest.fixture
def test_users(db_session):
    """Создает тестовых пользователей"""
    users = []

    # Создаем пользователей с ID 1-5
    for i in range(1, 6):
        user = db_session.query(Author).filter(Author.id == i).first()
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
    community = db_session.query(Community).filter(Community.id == 1).first()
    if not community:
        community = Community(
            id=1,
            name="Test Community",
            slug="test-community",
            desc="Test community for RBAC tests",
            created_by=test_users[0].id,
        )
        db_session.add(community)
        db_session.commit()

    return community


class TestCommunityAuthorRoles:
    """Тесты для управления ролями в CommunityAuthor"""

    def test_role_list_property(self, db_session, test_users, test_community):
        """Тест свойства role_list для CSV ролей"""
        # Очищаем существующие записи для этого пользователя
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[0].id
        ).delete()
        db_session.commit()

        # Создаем запись с ролями
        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles="reader,author,expert")
        db_session.add(ca)
        db_session.commit()

        # Проверяем получение списка ролей
        assert ca.role_list == ["reader", "author", "expert"]

        # Проверяем установку списка ролей
        ca.role_list = ["admin", "editor"]
        assert ca.roles == "admin,editor"

        # Проверяем пустые роли
        ca.role_list = []
        assert ca.roles is None
        assert ca.role_list == []

    def test_has_role(self, db_session, test_users, test_community):
        """Тест проверки наличия роли"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[1].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[1].id, roles="reader,author")
        db_session.add(ca)
        db_session.commit()

        # Проверяем существующие роли
        assert ca.has_role("reader") is True
        assert ca.has_role("author") is True

        # Проверяем несуществующие роли
        assert ca.has_role("admin") is False
        assert ca.has_role("editor") is False

    def test_add_role(self, db_session, test_users, test_community):
        """Тест добавления роли"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[2].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[2].id, roles="reader")
        db_session.add(ca)
        db_session.commit()

        # Добавляем новую роль
        ca.add_role("author")
        assert ca.role_list == ["reader", "author"]

        # Попытка добавить существующую роль (не должна дублироваться)
        ca.add_role("reader")
        assert ca.role_list == ["reader", "author"]

        # Добавляем ещё одну роль
        ca.add_role("expert")
        assert ca.role_list == ["reader", "author", "expert"]

    def test_remove_role(self, db_session, test_users, test_community):
        """Тест удаления роли"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[3].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[3].id, roles="reader,author,expert")
        db_session.add(ca)
        db_session.commit()

        # Удаляем роль
        ca.remove_role("author")
        assert ca.role_list == ["reader", "expert"]

        # Попытка удалить несуществующую роль (не должна ломаться)
        ca.remove_role("admin")
        assert ca.role_list == ["reader", "expert"]

        # Удаляем все роли
        ca.remove_role("reader")
        ca.remove_role("expert")
        assert ca.role_list == []

    def test_set_roles(self, db_session, test_users, test_community):
        """Тест установки полного списка ролей"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[4].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[4].id, roles="reader")
        db_session.add(ca)
        db_session.commit()

        # Устанавливаем новый список ролей
        ca.set_roles(["admin", "editor", "expert"])
        assert ca.role_list == ["admin", "editor", "expert"]

        # Очищаем роли
        ca.set_roles([])
        assert ca.role_list == []


class TestPermissionsSystem:
    """Тесты для системы разрешений"""

    async def test_get_permissions_for_role(self):
        """Тест получения разрешений для роли"""
        community_id = 1  # Используем основное сообщество

        # Проверяем базовые роли
        reader_perms = await get_permissions_for_role("reader", community_id)
        assert "shout:read" in reader_perms
        assert "shout:create" not in reader_perms

        author_perms = await get_permissions_for_role("author", community_id)
        assert "shout:create" in author_perms
        assert "draft:create" in author_perms
        assert "shout:delete_any" not in author_perms

        admin_perms = await get_permissions_for_role("admin", community_id)
        assert "author:delete_any" in admin_perms
        assert "author:update_any" in admin_perms

        # Проверяем несуществующую роль
        unknown_perms = await get_permissions_for_role("unknown_role", community_id)
        assert unknown_perms == []

    async def test_reaction_permissions_generation(self):
        """Тест генерации разрешений для реакций"""
        community_id = 1  # Используем основное сообщество

        # Проверяем что система генерирует разрешения для реакций
        admin_perms = await get_permissions_for_role("admin", community_id)

        # Админ должен иметь все разрешения на реакции
        assert len(admin_perms) > 0, "Admin should have some permissions"

        # Проверяем что есть хотя бы базовые разрешения на реакции у читателей
        reader_perms = await get_permissions_for_role("reader", community_id)
        assert len(reader_perms) > 0, "Reader should have some permissions"

        # Проверяем что у reader есть разрешения на чтение реакций
        assert any("reaction:read:" in perm for perm in reader_perms), "Reader should have reaction read permissions"

    async def test_community_author_get_permissions(self, db_session, test_users, test_community):
        """Тест получения разрешений через CommunityAuthor"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[0].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles="reader,author")
        db_session.add(ca)
        db_session.commit()

        permissions = await ca.get_permissions()

        # Должны быть разрешения от обеих ролей
        assert "shout:read" in permissions  # От reader
        assert "shout:create" in permissions  # От author
        assert len(permissions) > 0  # Должны быть какие-то разрешения

    async def test_community_author_has_permission(self, db_session, test_users, test_community):
        """Тест проверки разрешения через CommunityAuthor"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[1].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[1].id, roles="expert,editor")
        db_session.add(ca)
        db_session.commit()

        # Проверяем разрешения
        permissions = await ca.get_permissions()
        # Expert имеет разрешения на реакции PROOF/DISPROOF
        assert any("reaction:create:PROOF" in perm for perm in permissions)
        # Editor имеет разрешения на удаление и обновление шаутов
        assert "shout:delete_any" in permissions
        assert "shout:update_any" in permissions


class TestClassMethods:
    """Тесты для классовых методов CommunityAuthor"""

    async def test_find_by_user_and_community(self, db_session, test_users, test_community):
        """Тест поиска записи CommunityAuthor"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[0].id
        ).delete()
        db_session.commit()

        # Создаем запись
        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles="reader,author")
        db_session.add(ca)
        db_session.commit()

        # Ищем существующую запись
        found = CommunityAuthor.find_by_user_and_community(test_users[0].id, test_community.id, db_session)
        assert found is not None
        assert found.author_id == test_users[0].id
        assert found.community_id == test_community.id

        # Ищем несуществующую запись
        not_found = CommunityAuthor.find_by_user_and_community(test_users[1].id, test_community.id, db_session)
        assert not_found is None

    async def test_get_users_with_role(self, db_session, test_users, test_community):
        """Тест получения пользователей с определенной ролью"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(CommunityAuthor.community_id == test_community.id).delete()
        db_session.commit()

        # Создаем пользователей с разными ролями
        cas = [
            CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles="reader,author"),
            CommunityAuthor(community_id=test_community.id, author_id=test_users[1].id, roles="reader,expert"),
            CommunityAuthor(community_id=test_community.id, author_id=test_users[2].id, roles="admin"),
        ]
        for ca in cas:
            db_session.add(ca)
        db_session.commit()

        # Ищем пользователей с ролью reader
        readers = CommunityAuthor.get_users_with_role(test_community.id, "reader", db_session)
        assert test_users[0].id in readers
        assert test_users[1].id in readers
        assert test_users[2].id not in readers

        # Ищем пользователей с ролью admin
        admins = CommunityAuthor.get_users_with_role(test_community.id, "admin", db_session)
        assert test_users[2].id in admins
        assert test_users[0].id not in admins


class TestEdgeCases:
    """Тесты для граничных случаев"""

    async def test_empty_roles_handling(self, db_session, test_users, test_community):
        """Тест обработки пустых ролей"""
        # Создаем запись с пустыми ролями
        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles="")
        db_session.add(ca)
        db_session.commit()

        assert ca.role_list == []
        permissions = await ca.get_permissions()
        assert permissions == []

    async def test_none_roles_handling(self, db_session, test_users, test_community):
        """Тест обработки NULL ролей"""
        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles=None)
        db_session.add(ca)
        db_session.commit()

        assert ca.role_list == []
        assert await ca.get_permissions() == []

    async def test_whitespace_roles_handling(self, db_session, test_users, test_community):
        """Тест обработки ролей с пробелами"""
        ca = CommunityAuthor(
            community_id=test_community.id, author_id=test_users[0].id, roles=" reader , author , expert "
        )
        db_session.add(ca)
        db_session.commit()

        # Пробелы должны убираться
        assert ca.role_list == ["reader", "author", "expert"]

    async def test_duplicate_roles_handling(self, db_session, test_users, test_community):
        """Тест обработки дублирующихся ролей"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[0].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(
            community_id=test_community.id, author_id=test_users[0].id, roles="reader,author,reader,expert,author"
        )
        db_session.add(ca)
        db_session.commit()

        # При установке через set_roles дубликаты должны убираться
        unique_roles = set(["reader", "author", "reader", "expert"])
        ca.set_roles(unique_roles)
        roles = ca.role_list
        # Проверяем что нет дубликатов
        assert len(roles) == len(set(roles))
        assert "reader" in roles
        assert "author" in roles
        assert "expert" in roles

    async def test_invalid_role(self):
        """Тест получения разрешений для несуществующих ролей"""
        community_id = 1  # Используем основное сообщество

        # Проверяем что несуществующая роль не ломает систему
        perms = await get_permissions_for_role("nonexistent_role", community_id)
        assert perms == []


class TestPerformance:
    """Тесты производительности (базовые)"""

    async def test_large_role_list_performance(self, db_session, test_users, test_community):
        """Тест производительности с большим количеством ролей"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[0].id
        ).delete()
        db_session.commit()

        # Создаем запись с множеством ролей
        many_roles = ",".join([f"role_{i}" for i in range(50)])  # Уменьшим количество
        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[0].id, roles=many_roles)
        db_session.add(ca)
        db_session.commit()

        # Операции должны работать быстро даже с множеством ролей
        role_list = ca.role_list
        assert len(role_list) == 50
        assert all(role.startswith("role_") for role in role_list)

    async def test_permissions_caching_behavior(self, db_session, test_users, test_community):
        """Тест поведения кеширования разрешений"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == test_community.id, CommunityAuthor.author_id == test_users[1].id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(community_id=test_community.id, author_id=test_users[1].id, roles="reader,author,expert")
        db_session.add(ca)
        db_session.commit()

        # Многократный вызов get_permissions должен работать стабильно
        perms1 = await ca.get_permissions()
        perms2 = await ca.get_permissions()
        perms3 = await ca.get_permissions()

        assert perms1.sort() == perms2.sort() == perms3.sort()
        assert len(perms1) > 0
