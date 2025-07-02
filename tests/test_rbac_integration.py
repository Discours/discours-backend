"""
Тесты интеграции RBAC системы с существующими компонентами проекта.

Проверяет работу вспомогательных функций из orm/community.py
и интеграцию с GraphQL резолверами.
"""

import pytest

from auth.orm import Author
from orm.community import (
    Community,
    CommunityAuthor,
    assign_role_to_user,
    bulk_assign_roles,
    check_user_permission_in_community,
    get_user_roles_in_community,
    remove_role_from_user,
)
from services.rbac import get_permissions_for_role


@pytest.fixture
def integration_users(db_session):
    """Создает тестовых пользователей для интеграционных тестов"""
    users = []

    # Создаем пользователей с ID 100-105 для избежания конфликтов
    for i in range(100, 106):
        user = db_session.query(Author).filter(Author.id == i).first()
        if not user:
            user = Author(
                id=i,
                email=f"integration_user{i}@example.com",
                name=f"Integration User {i}",
                slug=f"integration-user-{i}",
            )
            user.set_password("password123")
            db_session.add(user)
        users.append(user)

    db_session.commit()
    return users


@pytest.fixture
def integration_community(db_session, integration_users):
    """Создает тестовое сообщество для интеграционных тестов"""
    community = db_session.query(Community).filter(Community.id == 100).first()
    if not community:
        community = Community(
            id=100,
            name="Integration Test Community",
            slug="integration-test-community",
            desc="Community for integration tests",
            created_by=integration_users[0].id,
        )
        db_session.add(community)
        db_session.commit()

    return community


@pytest.fixture(autouse=True)
def clean_community_authors(db_session, integration_community):
    """Автоматически очищает все записи CommunityAuthor для тестового сообщества перед каждым тестом"""
    # Очистка перед тестом - используем более агрессивную очистку
    try:
        db_session.query(CommunityAuthor).filter(CommunityAuthor.community_id == integration_community.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()

    # Дополнительная очистка всех записей для тестовых пользователей
    try:
        db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id.in_([100, 101, 102, 103, 104, 105])).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()

    yield  # Тест выполняется

    # Очистка после теста
    try:
        db_session.query(CommunityAuthor).filter(CommunityAuthor.community_id == integration_community.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


class TestHelperFunctions:
    """Тесты для вспомогательных функций RBAC"""

    def test_get_user_roles_in_community(self, db_session, integration_users, integration_community):
        """Тест функции получения ролей пользователя в сообществе"""
        # Назначаем роли через функции вместо прямого создания записи
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[0].id, "author", integration_community.id)
        assign_role_to_user(integration_users[0].id, "expert", integration_community.id)

        # Проверяем функцию
        roles = get_user_roles_in_community(integration_users[0].id, integration_community.id)
        assert "reader" in roles
        assert "author" in roles
        assert "expert" in roles

        # Проверяем для пользователя без ролей
        no_roles = get_user_roles_in_community(integration_users[1].id, integration_community.id)
        assert no_roles == []

    async def test_check_user_permission_in_community(self, db_session, integration_users, integration_community):
        """Тест функции проверки разрешения в сообществе"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[0].id, "author", integration_community.id)
        assign_role_to_user(integration_users[0].id, "expert", integration_community.id)

        # Проверяем разрешения
        assert (
            await check_user_permission_in_community(integration_users[0].id, "shout:create", integration_community.id)
            is True
        )

        assert (
            await check_user_permission_in_community(integration_users[0].id, "shout:read", integration_community.id) is True
        )

        # Проверяем для пользователя без ролей
        # Сначала проверим какие роли у пользователя
        user_roles = get_user_roles_in_community(integration_users[1].id, integration_community.id)
        print(f"[DEBUG] User {integration_users[1].id} roles: {user_roles}")

        result = await check_user_permission_in_community(integration_users[1].id, "shout:create", integration_community.id)
        print(f"[DEBUG] Permission check result: {result}")

        assert result is False

    def test_assign_role_to_user(self, db_session, integration_users, integration_community):
        """Тест функции назначения роли пользователю"""
        # Назначаем роль пользователю без существующих ролей
        result = assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assert result is True

        # Проверяем что роль назначилась
        roles = get_user_roles_in_community(integration_users[0].id, integration_community.id)
        assert "reader" in roles

        # Назначаем ещё одну роль
        result = assign_role_to_user(integration_users[0].id, "author", integration_community.id)
        assert result is True

        roles = get_user_roles_in_community(integration_users[0].id, integration_community.id)
        assert "reader" in roles
        assert "author" in roles

        # Попытка назначить существующую роль
        result = assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assert result is False  # Роль уже есть

    def test_remove_role_from_user(self, db_session, integration_users, integration_community):
        """Тест функции удаления роли у пользователя"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[1].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[1].id, "author", integration_community.id)
        assign_role_to_user(integration_users[1].id, "expert", integration_community.id)

        # Удаляем роль
        result = remove_role_from_user(integration_users[1].id, "author", integration_community.id)
        assert result is True

        # Проверяем что роль удалилась
        roles = get_user_roles_in_community(integration_users[1].id, integration_community.id)
        assert "author" not in roles
        assert "reader" in roles
        assert "expert" in roles

        # Попытка удалить несуществующую роль
        result = remove_role_from_user(integration_users[1].id, "admin", integration_community.id)
        assert result is False

    async def test_get_all_community_members_with_roles(self, db_session, integration_users: list[Author], integration_community: Community):
        """Тест функции получения всех участников сообщества с ролями"""
        # Назначаем роли нескольким пользователям через функции
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[0].id, "author", integration_community.id)

        assign_role_to_user(integration_users[1].id, "expert", integration_community.id)
        assign_role_to_user(integration_users[1].id, "editor", integration_community.id)

        assign_role_to_user(integration_users[2].id, "admin", integration_community.id)

        # Получаем участников
        members = integration_community.get_community_members(with_roles=True)

        assert len(members) == 3

        # Проверяем структуру данных
        for member in members:
            assert "author_id" in member
            assert "roles" in member
            assert "permissions" in member
            assert "joined_at" in member

        # Проверяем конкретного участника
        admin_member = next(m for m in members if m["author_id"] == integration_users[2].id)
        assert "admin" in admin_member["roles"]
        assert len(admin_member["permissions"]) > 0

    def test_bulk_assign_roles(self, db_session, integration_users: list[Author], integration_community: Community):
        """Тест функции массового назначения ролей"""
        # Подготавливаем данные для массового назначения
        user_role_pairs = [
            (integration_users[0].id, "reader"),
            (integration_users[1].id, "author"),
            (integration_users[2].id, "expert"),
            (integration_users[3].id, "editor"),
            (integration_users[4].id, "admin"),
        ]

        # Выполняем массовое назначение
        result = bulk_assign_roles(user_role_pairs, integration_community.id)

        # Проверяем результат
        assert result["success"] == 5
        assert result["failed"] == 0

        # Проверяем что роли назначились
        for user_id, expected_role in user_role_pairs:
            roles = get_user_roles_in_community(user_id, integration_community.id)
            assert expected_role in roles


class TestRoleHierarchy:
    """Тесты иерархии ролей и наследования разрешений"""

    async def test_role_inheritance(self, integration_community):
        """Тест наследования разрешений между ролями"""
        # Читатель имеет базовые разрешения
        reader_perms = set(await get_permissions_for_role("reader", integration_community.id))

        # Автор должен иметь все разрешения читателя + свои
        author_perms = set(await get_permissions_for_role("author", integration_community.id))

        # Проверяем что автор имеет базовые разрешения читателя
        basic_read_perms = {"shout:read", "topic:read"}
        assert basic_read_perms.issubset(author_perms)

        # Админ должен иметь максимальные разрешения
        admin_perms = set(await get_permissions_for_role("admin", integration_community.id))
        assert len(admin_perms) >= len(author_perms)
        assert len(admin_perms) >= len(reader_perms)

    async def test_permission_aggregation(self, db_session, integration_users, integration_community):
        """Тест агрегации разрешений от нескольких ролей"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[0].id, "author", integration_community.id)
        assign_role_to_user(integration_users[0].id, "expert", integration_community.id)

        # Получаем объект CommunityAuthor для проверки агрегированных разрешений
        from services.db import local_session

        with local_session() as session:
            ca = CommunityAuthor.find_by_user_and_community(integration_users[0].id, integration_community.id, session)

            # Получаем агрегированные разрешения
            all_permissions = await ca.get_permissions()

            # Проверяем что есть разрешения от всех ролей
            reader_perms = await get_permissions_for_role("reader", integration_community.id)
            author_perms = await get_permissions_for_role("author", integration_community.id)
            expert_perms = await get_permissions_for_role("expert", integration_community.id)

            # Все разрешения от отдельных ролей должны быть в общем списке
            for perm in reader_perms:
                assert perm in all_permissions
            for perm in author_perms:
                assert perm in all_permissions
            for perm in expert_perms:
                assert perm in all_permissions


class TestCommunityMethods:
    """Тесты методов Community для работы с ролями"""

    def test_community_get_user_roles(self, db_session, integration_users, integration_community):
        """Тест получения ролей пользователя через сообщество"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[0].id, "author", integration_community.id)
        assign_role_to_user(integration_users[0].id, "expert", integration_community.id)

        # Проверяем через метод сообщества
        user_roles = integration_community.get_user_roles(integration_users[0].id)
        assert "reader" in user_roles
        assert "author" in user_roles
        assert "expert" in user_roles

        # Проверяем для пользователя без ролей
        no_roles = integration_community.get_user_roles(integration_users[1].id)
        assert no_roles == []

    def test_community_has_user_role(self, db_session, integration_users, integration_community):
        """Тест проверки роли пользователя в сообществе"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[1].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[1].id, "author", integration_community.id)

        # Проверяем существующие роли
        assert integration_community.has_user_role(integration_users[1].id, "reader") is True
        assert integration_community.has_user_role(integration_users[1].id, "author") is True

        # Проверяем несуществующие роли
        assert integration_community.has_user_role(integration_users[1].id, "admin") is False

    def test_community_add_user_role(self, db_session, integration_users, integration_community):
        """Тест добавления роли пользователю через сообщество"""
        # Добавляем роль пользователю без записи
        integration_community.add_user_role(integration_users[0].id, "reader")

        # Проверяем что роль добавилась
        roles = integration_community.get_user_roles(integration_users[0].id)
        assert "reader" in roles

        # Добавляем ещё одну роль
        integration_community.add_user_role(integration_users[0].id, "author")
        roles = integration_community.get_user_roles(integration_users[0].id)
        assert "reader" in roles
        assert "author" in roles

    def test_community_remove_user_role(self, db_session, integration_users, integration_community):
        """Тест удаления роли у пользователя через сообщество"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[1].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[1].id, "author", integration_community.id)
        assign_role_to_user(integration_users[1].id, "expert", integration_community.id)

        # Удаляем роль
        integration_community.remove_user_role(integration_users[1].id, "author")
        roles = integration_community.get_user_roles(integration_users[1].id)
        assert "author" not in roles
        assert "reader" in roles
        assert "expert" in roles

    def test_community_set_user_roles(self, db_session, integration_users, integration_community):
        """Тест установки ролей пользователя через сообщество"""
        # Устанавливаем роли пользователю без записи
        integration_community.set_user_roles(integration_users[2].id, ["admin", "editor"])
        roles = integration_community.get_user_roles(integration_users[2].id)
        assert set(roles) == {"admin", "editor"}

        # Меняем роли
        integration_community.set_user_roles(integration_users[2].id, ["reader"])
        roles = integration_community.get_user_roles(integration_users[2].id)
        assert roles == ["reader"]

        # Очищаем роли
        integration_community.set_user_roles(integration_users[2].id, [])
        roles = integration_community.get_user_roles(integration_users[2].id)
        assert roles == []

    async def test_community_get_members(self, db_session, integration_users: list[Author], integration_community: Community):
        """Тест получения участников сообщества"""
        # Назначаем роли через функции
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)
        assign_role_to_user(integration_users[0].id, "author", integration_community.id)

        assign_role_to_user(integration_users[1].id, "expert", integration_community.id)

        # Получаем участников без ролей
        members = integration_community.get_community_members(with_roles=False)
        for member in members:
            assert "author_id" in member
            assert "joined_at" in member
            assert "roles" not in member

        # Получаем участников с ролями
        members_with_roles = integration_community.get_community_members(with_roles=True)
        for member in members_with_roles:
            assert "author_id" in member
            assert "joined_at" in member
            assert "roles" in member
            assert "permissions" in member


class TestEdgeCasesIntegration:
    """Тесты граничных случаев интеграции"""

    async def test_nonexistent_community(self, integration_users):
        """Тест работы с несуществующим сообществом"""
        # Функции должны корректно обрабатывать несуществующие сообщества
        roles = get_user_roles_in_community(integration_users[0].id, 99999)
        assert roles == []

        has_perm = await check_user_permission_in_community(integration_users[0].id, "shout:read", 99999)
        assert has_perm is False

    async def test_nonexistent_user(self, integration_community):
        """Тест работы с несуществующим пользователем"""
        # Функции должны корректно обрабатывать несуществующих пользователей
        roles = get_user_roles_in_community(99999, integration_community.id)
        assert roles == []

        has_perm = await check_user_permission_in_community(99999, "shout:read", integration_community.id)
        assert has_perm is False

    async def test_empty_permission_check(self, db_session, integration_users, integration_community):
        """Тест проверки пустых разрешений"""
        # Создаем пользователя без ролей через прямое создание записи (пустые роли)
        ca = CommunityAuthor(community_id=integration_community.id, author_id=integration_users[0].id, roles="")
        db_session.add(ca)
        db_session.commit()

        # Проверяем что нет разрешений
        assert ca.has_permission("shout:read") is False
        assert ca.has_permission("shout:create") is False
        permissions = await ca.get_permissions()
        assert len(permissions) == 0


class TestDataIntegrity:
    """Тесты целостности данных"""

    def test_joined_at_field(self, db_session, integration_users, integration_community):
        """Тест что поле joined_at корректно заполняется"""
        # Назначаем роль через функцию
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)

        # Получаем созданную запись
        from services.db import local_session

        with local_session() as session:
            ca = CommunityAuthor.find_by_user_and_community(integration_users[0].id, integration_community.id, session)

            # Проверяем что joined_at заполнено
            assert ca.joined_at is not None
            assert isinstance(ca.joined_at, int)
            assert ca.joined_at > 0

    def test_roles_field_constraints(self, db_session, integration_users, integration_community):
        """Тест ограничений поля roles"""
        # Тест с пустой строкой ролей
        ca = CommunityAuthor(community_id=integration_community.id, author_id=integration_users[0].id, roles="")
        db_session.add(ca)
        db_session.commit()

        assert ca.role_list == []

        # Тест с None
        ca.roles = None
        db_session.commit()
        assert ca.role_list == []

    def test_unique_constraints(self, db_session, integration_users, integration_community):
        """Тест уникальных ограничений"""
        # Создаем первую запись через функцию
        assign_role_to_user(integration_users[0].id, "reader", integration_community.id)

        # Попытка создать дублирующуюся запись должна вызвать ошибку
        ca2 = CommunityAuthor(community_id=integration_community.id, author_id=integration_users[0].id, roles="author")
        db_session.add(ca2)

        with pytest.raises(Exception):  # IntegrityError или подобная
            db_session.commit()


class TestCommunitySettings:
    """Тесты настроек сообщества для ролей"""

    def test_default_roles_management(self, db_session, integration_community):
        """Тест управления дефолтными ролями"""
        # Проверяем дефолтные роли по умолчанию
        default_roles = integration_community.get_default_roles()
        assert "reader" in default_roles

        # Устанавливаем новые дефолтные роли
        integration_community.set_default_roles(["reader", "author"])
        new_default_roles = integration_community.get_default_roles()
        assert set(new_default_roles) == {"reader", "author"}

    def test_available_roles_management(self, integration_community):
        """Тест управления доступными ролями"""
        # Проверяем доступные роли по умолчанию
        available_roles = integration_community.get_available_roles()
        expected_roles = ["reader", "author", "artist", "expert", "editor", "admin"]
        assert set(available_roles) == set(expected_roles)

    def test_assign_default_roles(self, db_session, integration_users, integration_community):
        """Тест назначения дефолтных ролей"""
        # Устанавливаем дефолтные роли
        integration_community.set_default_roles(["reader", "author"])

        # Назначаем дефолтные роли пользователю
        integration_community.assign_default_roles_to_user(integration_users[0].id)

        # Проверяем что роли назначились
        roles = integration_community.get_user_roles(integration_users[0].id)
        assert set(roles) == {"reader", "author"}
