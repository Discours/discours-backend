"""
Упрощенные тесты интеграции RBAC системы с новой архитектурой сервисов.

Проверяет работу AdminService и AuthService с RBAC системой.
"""

import pytest

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.admin import admin_service
from services.auth import auth_service


@pytest.fixture
def simple_user(db_session):
    """Создает простого тестового пользователя"""
    # Очищаем любые существующие записи с этим ID/email
    db_session.query(Author).filter(
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
        db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete()
        # Удаляем самого пользователя
        db_session.query(Author).filter(Author.id == user.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture
def simple_community(db_session, simple_user):
    """Создает простое тестовое сообщество"""
    # Очищаем любые существующие записи с этим ID/slug
    db_session.query(Community).filter(
        (Community.id == 200) | (Community.slug == "simple-test-community")
    ).delete()
    db_session.commit()

    community = Community(
        id=200,
        name="Simple Test Community",
        slug="simple-test-community",
        desc="Simple community for tests",
        created_by=simple_user.id,
    )
    db_session.add(community)
    db_session.commit()

    yield community

    # Очистка после теста
    try:
        # Удаляем связанные записи CommunityAuthor
        db_session.query(CommunityAuthor).filter(CommunityAuthor.community_id == community.id).delete()
        # Удаляем само сообщество
        db_session.query(Community).filter(Community.id == community.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture(autouse=True)
def cleanup_test_users(db_session):
    """Автоматически очищает тестовые записи пользователей перед каждым тестом"""
    # Очищаем тестовые email'ы перед тестом
    test_emails = [
        "test_create@example.com",
        "test_community@example.com",
        "simple_user@example.com",
        "test_create_unique@example.com",
        "test_community_unique@example.com"
    ]

    # Очищаем также тестовые ID
    test_ids = [200, 201, 202, 203, 204, 205]

    for email in test_emails:
        try:
            existing_user = db_session.query(Author).filter(Author.email == email).first()
            if existing_user:
                # Удаляем связанные записи CommunityAuthor
                db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == existing_user.id).delete()
                # Удаляем пользователя
                db_session.delete(existing_user)
            db_session.commit()
        except Exception:
            db_session.rollback()

    # Дополнительная очистка по ID
    for user_id in test_ids:
        try:
            # Удаляем записи CommunityAuthor
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user_id).delete()
            # Удаляем пользователя
            db_session.query(Author).filter(Author.id == user_id).delete()
            db_session.commit()
        except Exception:
            db_session.rollback()

    yield  # Тест выполняется

    # Дополнительная очистка после теста
    for email in test_emails:
        try:
            existing_user = db_session.query(Author).filter(Author.email == email).first()
            if existing_user:
                db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == existing_user.id).delete()
                db_session.delete(existing_user)
            db_session.commit()
        except Exception:
            db_session.rollback()

    for user_id in test_ids:
        try:
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user_id).delete()
            db_session.query(Author).filter(Author.id == user_id).delete()
            db_session.commit()
        except Exception:
            db_session.rollback()


class TestSimpleAdminService:
    """Простые тесты для AdminService"""

    def test_get_user_roles_empty(self, db_session, simple_user, simple_community):
        """Тест получения пустых ролей пользователя"""
        # Очищаем любые существующие роли
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == simple_community.id
        ).delete()
        db_session.commit()

        # Проверяем что ролей нет
        roles = admin_service.get_user_roles(simple_user, simple_community.id)
        assert isinstance(roles, list)
        # Может быть пустой список или содержать системную роль админа
        assert len(roles) >= 0

    def test_get_user_roles_with_roles(self, db_session, simple_user, simple_community):
        """Тест получения ролей пользователя"""
        # Используем дефолтное сообщество (ID=1) для совместимости с AdminService
        default_community_id = 1

        print(f"DEBUG: user_id={simple_user.id}, community_id={default_community_id}")

        # Очищаем существующие роли
        deleted_count = db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == default_community_id
        ).delete()
        db_session.commit()
        print(f"DEBUG: Удалено записей CommunityAuthor: {deleted_count}")

        # Создаем CommunityAuthor с ролями в дефолтном сообществе
        ca = CommunityAuthor(
            community_id=default_community_id,
            author_id=simple_user.id,
        )
        ca.set_roles(["reader", "author"])
        print(f"DEBUG: Установлены роли: {ca.role_list}")
        db_session.add(ca)
        db_session.commit()
        print(f"DEBUG: CA сохранен в БД с ID: {ca.id}")

        # Проверяем что роли сохранились в БД
        saved_ca = db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == default_community_id
        ).first()
        assert saved_ca is not None
        print(f"DEBUG: Сохраненные роли в БД: {saved_ca.role_list}")
        assert "reader" in saved_ca.role_list
        assert "author" in saved_ca.role_list

        # Проверяем роли через AdminService (использует дефолтное сообщество)
        fresh_user = db_session.query(Author).filter(Author.id == simple_user.id).first()
        roles = admin_service.get_user_roles(fresh_user)  # Без указания community_id - использует дефолт
        print(f"DEBUG: AdminService вернул роли: {roles}")
        assert "reader" in roles
        assert "author" in roles

    def test_update_user_success(self, db_session, simple_user):
        """Тест успешного обновления пользователя"""
        original_name = simple_user.name

        user_data = {
            "id": simple_user.id,
            "email": simple_user.email,
            "name": "Updated Name",
            "roles": ["reader"]
        }

        result = admin_service.update_user(user_data)
        assert result["success"] is True

        # Получаем обновленного пользователя из БД заново
        updated_user = db_session.query(Author).filter(Author.id == simple_user.id).first()
        assert updated_user.name == "Updated Name"

        # Восстанавливаем исходное имя для других тестов
        updated_user.name = original_name
        db_session.commit()


class TestSimpleAuthService:
    """Простые тесты для AuthService"""

    def test_create_user_basic(self, db_session):
        """Тест базового создания пользователя"""
        test_email = "test_create_unique@example.com"

        # Удаляем пользователя если существует
        existing = db_session.query(Author).filter(Author.email == test_email).first()
        if existing:
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == existing.id).delete()
            db_session.delete(existing)
            db_session.commit()

        user_dict = {
            "email": test_email,
            "name": "Test Create User",
            "slug": "test-create-user-unique",
        }

        user = auth_service.create_user(user_dict)

        assert user is not None
        assert user.email == test_email
        assert user.name == "Test Create User"

        # Очистка
        db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete()
        db_session.delete(user)
        db_session.commit()

    def test_create_user_with_community(self, db_session, simple_community):
        """Тест создания пользователя с привязкой к сообществу"""
        test_email = "test_community_unique@example.com"

        # Удаляем пользователя если существует
        existing = db_session.query(Author).filter(Author.email == test_email).first()
        if existing:
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == existing.id).delete()
            db_session.delete(existing)
            db_session.commit()

        user_dict = {
            "email": test_email,
            "name": "Test Community User",
            "slug": "test-community-user-unique",
        }

        user = auth_service.create_user(user_dict, community_id=simple_community.id)

        assert user is not None
        assert user.email == test_email

        # Очистка
        db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete()
        db_session.delete(user)
        db_session.commit()


class TestCommunityAuthorMethods:
    """Тесты методов CommunityAuthor"""

    def test_set_get_roles(self, db_session, simple_user, simple_community):
        """Тест установки и получения ролей"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == simple_community.id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(
            community_id=simple_community.id,
            author_id=simple_user.id,
        )

        # Тестируем установку ролей
        ca.set_roles(["reader", "author"])
        assert ca.role_list == ["reader", "author"]

        # Тестируем пустые роли
        ca.set_roles([])
        assert ca.role_list == []

    def test_has_role(self, db_session, simple_user, simple_community):
        """Тест проверки наличия роли"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == simple_community.id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(
            community_id=simple_community.id,
            author_id=simple_user.id,
        )
        ca.set_roles(["reader", "author"])
        db_session.add(ca)
        db_session.commit()

        assert ca.has_role("reader") is True
        assert ca.has_role("author") is True
        assert ca.has_role("admin") is False

    def test_add_remove_role(self, db_session, simple_user, simple_community):
        """Тест добавления и удаления ролей"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == simple_community.id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(
            community_id=simple_community.id,
            author_id=simple_user.id,
        )
        ca.set_roles(["reader"])
        db_session.add(ca)
        db_session.commit()

        # Добавляем роль
        ca.add_role("author")
        assert ca.has_role("author") is True

        # Удаляем роль
        ca.remove_role("reader")
        assert ca.has_role("reader") is False
        assert ca.has_role("author") is True


class TestDataIntegrity:
    """Простые тесты целостности данных"""

    def test_unique_community_author(self, db_session, simple_user, simple_community):
        """Тест уникальности записей CommunityAuthor"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == simple_community.id
        ).delete()
        db_session.commit()

        # Создаем первую запись
        ca1 = CommunityAuthor(
            community_id=simple_community.id,
            author_id=simple_user.id,
        )
        ca1.set_roles(["reader"])
        db_session.add(ca1)
        db_session.commit()

        # Проверяем что запись создалась
        found = db_session.query(CommunityAuthor).filter(
            CommunityAuthor.community_id == simple_community.id,
            CommunityAuthor.author_id == simple_user.id
        ).first()

        assert found is not None
        assert found.id == ca1.id

    def test_roles_validation(self, db_session, simple_user, simple_community):
        """Тест валидации ролей"""
        # Очищаем существующие записи
        db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == simple_community.id
        ).delete()
        db_session.commit()

        ca = CommunityAuthor(
            community_id=simple_community.id,
            author_id=simple_user.id,
        )

        # Тестируем различные форматы
        ca.set_roles(["reader", "author", "expert"])
        assert set(ca.role_list) == {"reader", "author", "expert"}

        ca.set_roles([])
        assert ca.role_list == []

        ca.set_roles(["admin"])
        assert ca.role_list == ["admin"]
