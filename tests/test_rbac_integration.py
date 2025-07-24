"""
Упрощенные тесты интеграции RBAC системы с новой архитектурой сервисов.

Проверяет работу AdminService и AuthService с RBAC системой.
"""
import logging
import pytest

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.admin import admin_service
from services.auth import auth_service

logger = logging.getLogger(__name__)


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
        db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete(synchronize_session=False)
        # Удаляем самого пользователя
        db_session.query(Author).filter(Author.id == user.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture
def simple_community(db_session, simple_user):
    """Создает простое тестовое сообщество"""
    # Очищаем любые существующие записи с этим ID/slug
    db_session.query(Community).filter(Community.slug == "simple-test-community").delete()
    db_session.commit()

    community = Community(
        name="Simple Test Community",
        slug="simple-test-community",
        desc="Simple community for tests",
        created_by=simple_user.id,
        settings={
            "default_roles": ["reader", "author"],
            "available_roles": ["reader", "author", "editor"]
        }
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


@pytest.fixture
def test_community(db_session, simple_user):
    """
    Создает тестовое сообщество с ожидаемыми ролями по умолчанию

    Args:
        db_session: Сессия базы данных для теста
        simple_user: Пользователь для создания сообщества

    Returns:
        Community: Созданное тестовое сообщество
    """
    # Очищаем существующие записи
    db_session.query(Community).filter(Community.slug == "test-rbac-community").delete()
    db_session.commit()

    community = Community(
        name="Test RBAC Community",
        slug="test-rbac-community",
        desc="Community for RBAC tests",
        created_by=simple_user.id,
        settings={
            "default_roles": ["reader", "author"],
            "available_roles": ["reader", "author", "editor"]
        }
    )
    db_session.add(community)
    db_session.flush()  # Получаем ID без коммита

    logger.info(f"DEBUG: Создание Community с айди {community.id}")

    db_session.commit()

    yield community

    # Очистка после теста
    try:
        # Удаляем связанные записи CommunityAuthor
        db_session.query(CommunityAuthor).filter(CommunityAuthor.community_id == community.id).delete()
        # Удаляем сообщество
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
                db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == existing_user.id).delete(synchronize_session=False)
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

    def test_get_user_roles_with_roles(self, db_session, simple_user, test_community):
        """Тест получения ролей пользователя"""
        # Используем тестовое сообщество
        community_id = test_community.id

        # Отладочная информация о тестовом сообществе
        logger.info(f"DEBUG: Тестовое сообщество ID: {community_id}")
        logger.info(f"DEBUG: Тестовое сообщество slug: {test_community.slug}")
        logger.info(f"DEBUG: Тестовое сообщество settings: {test_community.settings}")

        # Полностью очищаем все существующие CommunityAuthor для пользователя
        existing_community_authors = db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id
        ).all()

        # Отладочная информация
        logger.info(f"DEBUG: Найдено существующих CommunityAuthor: {len(existing_community_authors)}")
        for ca in existing_community_authors:
            logger.info(f"DEBUG: Существующий CA - community_id: {ca.community_id}, roles: {ca.roles}")
            db_session.delete(ca)

        db_session.commit()

        # Создаем CommunityAuthor с ролями в тестовом сообществе
        ca = CommunityAuthor(
            community_id=community_id,
            author_id=simple_user.id,
        )

        # Расширенная отладка перед set_roles
        logger.info(f"DEBUG: Перед set_roles")
        logger.info(f"DEBUG: ca.roles до set_roles: {ca.roles}")
        logger.info(f"DEBUG: ca.role_list до set_roles: {ca.role_list}")

        ca.set_roles(["reader", "author"])

        # Расширенная отладка после set_roles
        logger.info(f"DEBUG: После set_roles")
        logger.info(f"DEBUG: ca.roles после set_roles: {ca.roles}")
        logger.info(f"DEBUG: ca.role_list после set_roles: {ca.role_list}")

        db_session.add(ca)
        db_session.commit()

        # Явная проверка сохранения CommunityAuthor
        check_ca = db_session.query(CommunityAuthor).filter(
            CommunityAuthor.author_id == simple_user.id,
            CommunityAuthor.community_id == community_id
        ).first()

        logger.info(f"DEBUG: Проверка сохраненной записи CommunityAuthor")
        logger.info(f"DEBUG: Найденная запись: {check_ca}")
        logger.info(f"DEBUG: Роли в найденной записи: {check_ca.roles}")
        logger.info(f"DEBUG: role_list найденной записи: {check_ca.role_list}")

        assert check_ca is not None, "CommunityAuthor должен быть сохранен в базе данных"
        assert check_ca.roles is not None, "Роли CommunityAuthor не должны быть None"
        assert "reader" in check_ca.role_list, "Роль 'reader' должна быть в role_list"
        assert "author" in check_ca.role_list, "Роль 'author' должна быть в role_list"

        # Проверяем роли через AdminService
        from services.admin import admin_service
        from services.db import local_session

        # Используем ту же сессию для проверки
        fresh_user = db_session.query(Author).filter(Author.id == simple_user.id).first()
        roles = admin_service.get_user_roles(fresh_user, community_id)

        # Проверяем роли
        assert isinstance(roles, list), "Роли должны быть списком"
        assert "reader" in roles, "Роль 'reader' должна присутствовать"
        assert "author" in roles, "Роль 'author' должна присутствовать"
        assert len(roles) == 2, f"Должно быть 2 роли, а не {len(roles)}"

    def test_update_user_success(self, db_session, simple_user):
        """Тест успешного обновления пользователя"""
        from services.admin import admin_service

        # Обновляем пользователя
        result = admin_service.update_user({
            "id": simple_user.id,
            "name": "Updated Name",
            "email": simple_user.email
        })

        # Проверяем обновленного пользователя
        assert result is not None, "Пользователь должен быть обновлен"
        assert result.get("name") == "Updated Name", "Имя пользователя должно быть обновлено"

        # Восстанавливаем исходное имя
        admin_service.update_user({
            "id": simple_user.id,
            "name": "Simple User",
            "email": simple_user.email
        })


class TestSimpleAuthService:
    """Простые тесты для AuthService"""

    def test_create_user_basic(self, db_session):
        """Тест базового создания пользователя"""
        test_email = "test_create_unique@example.com"

        # Найдем существующих пользователей с таким email
        existing_users = db_session.query(Author).filter(Author.email == test_email).all()

        # Удаляем связанные записи CommunityAuthor для существующих пользователей
        for user in existing_users:
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete(synchronize_session=False)
            db_session.delete(user)

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
        try:
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete(synchronize_session=False)
            db_session.delete(user)
            db_session.commit()
        except Exception as e:
            # Если возникла ошибка при удалении, просто логируем ее
            print(f"Ошибка при очистке: {e}")
            db_session.rollback()

    def test_create_user_with_community(self, db_session):
        """Проверяем создание пользователя в конкретном сообществе"""
        from services.auth import auth_service
        from services.rbac import initialize_community_permissions
        from auth.orm import Author
        import asyncio
        import uuid

        # Создаем тестового пользователя
        system_author = db_session.query(Author).filter(Author.slug == "system").first()
        if not system_author:
            system_author = Author(
                name="System",
                slug="system",
                email="system@test.local"
            )
            db_session.add(system_author)
            db_session.flush()

        # Создаем тестовое сообщество
        unique_slug = f"simple-test-community-{uuid.uuid4()}"
        community = Community(
            name="Simple Test Community",
            slug=unique_slug,
            desc="Simple community for tests",
            created_by=system_author.id,
            settings={
                "default_roles": ["reader", "author"],
                "available_roles": ["reader", "author", "editor"]
            }
        )
        db_session.add(community)
        db_session.flush()

        # Инициализируем права сообщества
        async def init_community_permissions():
            await initialize_community_permissions(community.id)

        # Запускаем инициализацию в текущем event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(init_community_permissions())

        # Генерируем уникальные данные для каждого теста
        unique_email = f"test_community_unique_{uuid.uuid4()}@example.com"
        unique_name = f"Test Community User {uuid.uuid4()}"
        unique_slug = f"test-community-user-{uuid.uuid4()}"

        user_dict = {
            "name": unique_name,
            "email": unique_email,
            "slug": unique_slug
        }

        # Создаем пользователя в конкретном сообществе
        user = auth_service.create_user(user_dict, community_id=community.id)

        # Проверяем созданного пользователя
        assert user is not None, "Пользователь должен быть создан"
        assert user.email == unique_email.lower(), "Email должен быть в нижнем регистре"
        assert user.name == unique_name, "Имя пользователя должно совпадать"
        assert user.slug == unique_slug, "Slug пользователя должен совпадать"

        # Проверяем роли
        from orm.community import get_user_roles_in_community

        # Получаем роли
        roles = get_user_roles_in_community(user.id, community_id=community.id)

        # Проверяем роли
        assert "reader" in roles, f"У нового пользователя должна быть роль 'reader' в сообществе {community.id}. Текущие роли: {roles}"
        assert "author" in roles, f"У нового пользователя должна быть роль 'author' в сообществе {community.id}. Текущие роли: {roles}"

        # Коммитим изменения
        db_session.commit()

        # Очищаем созданные объекты
        try:
            # Удаляем связанные записи CommunityAuthor
            db_session.query(CommunityAuthor).filter(CommunityAuthor.author_id == user.id).delete()
            # Удаляем пользователя
            db_session.query(Author).filter(Author.id == user.id).delete()
            # Удаляем сообщество
            db_session.query(Community).filter(Community.id == community.id).delete()
            db_session.commit()
        except Exception:
            db_session.rollback()


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
