"""
Тесты для исправлений в админ-панели.

Проверяет работу обновленных компонентов, исправления в системе ролей
и корректность работы интерфейса управления пользователями.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.db import local_session


# Используем общую фикстуру из conftest.py


@pytest.fixture
def test_community(db_session, test_users):
    """Создает тестовое сообщество для админ-панели"""
    community = Community(
        id=100,
        name="Admin Test Community",
        slug="admin-test-community",
        desc="Test community for admin panel tests",
        created_by=test_users[0].id,
        created_at=int(time.time())
    )
    db_session.add(community)
    db_session.commit()
    return community


@pytest.fixture
def admin_user_with_roles(db_session, test_users, test_community):
    """Создает пользователя с ролями администратора"""
    user = test_users[0]

    # Создаем CommunityAuthor с ролями администратора
    ca = CommunityAuthor(
        community_id=test_community.id,
        author_id=user.id,
        roles="admin,editor,author"
    )
    db_session.add(ca)
    db_session.commit()

    return user


@pytest.fixture
def regular_user_with_roles(db_session, test_users, test_community):
    """Создает обычного пользователя с ролями"""
    user = test_users[1]

    # Создаем CommunityAuthor с обычными ролями
    ca = CommunityAuthor(
        community_id=test_community.id,
        author_id=user.id,
        roles="reader,author"
    )
    db_session.add(ca)
    db_session.commit()

    return user


class TestAdminUserManagement:
    """Тесты для управления пользователями в админ-панели"""

    def test_admin_user_creation(self, db_session, test_users):
        """Тест создания пользователя через админ-панель"""
        user = test_users[0]

        # Проверяем что пользователь создан
        assert user.id == 1
        assert user.email is not None
        assert user.name is not None
        assert user.slug is not None

    def test_user_role_assignment(self, db_session, test_users, test_community):
        """Тест назначения ролей пользователю"""
        user = test_users[0]

        # Назначаем роли
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="admin,editor"
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что роли назначены
        assert ca.has_role("admin")
        assert ca.has_role("editor")
        assert not ca.has_role("reader")

    def test_user_role_removal(self, db_session, test_users, test_community):
        """Тест удаления ролей пользователя"""
        user = test_users[0]

        # Создаем пользователя с ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="admin,editor,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Удаляем роль
        ca.remove_role("editor")
        db_session.commit()

        # Проверяем что роль удалена
        assert ca.has_role("admin")
        assert not ca.has_role("editor")
        assert ca.has_role("author")

    def test_user_profile_update(self, db_session, test_users):
        """Тест обновления профиля пользователя"""
        user = test_users[0]

        # Обновляем данные пользователя
        user.email = "updated@example.com"
        user.name = "Updated Name"
        user.slug = "updated-slug"
        db_session.commit()

        # Проверяем что данные обновлены
        updated_user = db_session.query(Author).where(Author.id == user.id).first()
        assert updated_user.email == "updated@example.com"
        assert updated_user.name == "Updated Name"
        assert updated_user.slug == "updated-slug"


class TestRoleSystemFixes:
    """Тесты для исправлений в системе ролей"""

    def test_system_admin_role_handling(self, db_session, test_users, test_community):
        """Тест обработки системной роли администратора"""
        user = test_users[0]

        # Создаем пользователя с системной ролью admin
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="admin"
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что системная роль обрабатывается корректно
        assert ca.has_role("admin")

        # Удаляем системную роль (в текущей реализации это разрешено)
        ca.remove_role("admin")
        db_session.commit()

        # Проверяем что роль была удалена
        assert not ca.has_role("admin")

    def test_role_validation(self, db_session, test_users, test_community):
        """Тест валидации ролей"""
        user = test_users[0]

        # Создаем пользователя с валидными ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="reader,author,expert"
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что все роли валидны
        valid_roles = ["reader", "author", "expert", "editor", "admin"]
        for role in ca.role_list:
            assert role in valid_roles

    def test_empty_roles_handling(self, db_session, test_users, test_community):
        """Тест обработки пустых ролей"""
        user = test_users[0]

        # Создаем пользователя без ролей
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles=""
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что пустые роли обрабатываются корректно
        assert ca.role_list == []
        assert not ca.has_role("reader")

    def test_duplicate_roles_handling(self, db_session, test_users, test_community):
        """Тест обработки дублирующихся ролей"""
        user = test_users[0]

        # Создаем пользователя с дублирующимися ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="reader,reader,author,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что дублирующиеся роли обрабатываются корректно
        assert set(ca.role_list) == {"reader", "author"}


class TestCommunityManagement:
    """Тесты для управления сообществами"""

    def test_community_without_creator_handling(self, db_session, test_users):
        """Тест обработки сообщества без создателя"""
        # Создаем сообщество без создателя
        community = Community(
            id=200,
            name="Community Without Creator",
            slug="community-without-creator",
            desc="Test community without creator",
            created_by=None,
            created_at=int(time.time())
        )
        db_session.add(community)
        db_session.commit()

        # Проверяем что сообщество создано корректно
        assert community.created_by is None
        assert community.name == "Community Without Creator"

    def test_community_creator_assignment(self, db_session, test_users):
        """Тест назначения создателя сообществу"""
        # Создаем сообщество без создателя
        community = Community(
            id=201,
            name="Community for Creator Assignment",
            slug="community-creator-assignment",
            desc="Test community for creator assignment",
            created_by=None,
            created_at=int(time.time())
        )
        db_session.add(community)
        db_session.commit()

        # Назначаем создателя
        community.created_by = test_users[0].id
        db_session.commit()

        # Проверяем что создатель назначен
        assert community.created_by == test_users[0].id

    def test_community_followers_management(self, db_session, test_users, test_community):
        """Тест управления подписчиками сообщества"""
        from orm.community import CommunityFollower

        # Добавляем подписчиков
        follower1 = CommunityFollower(
            community=test_community.id,
            follower=test_users[0].id
        )
        follower2 = CommunityFollower(
            community=test_community.id,
            follower=test_users[1].id
        )

        db_session.add(follower1)
        db_session.add(follower2)
        db_session.commit()

        # Проверяем что подписчики добавлены
        followers = db_session.query(CommunityFollower).where(
            CommunityFollower.community == test_community.id
        ).all()

        assert len(followers) == 2
        follower_ids = [f.follower for f in followers]
        assert test_users[0].id in follower_ids
        assert test_users[1].id in follower_ids


class TestPermissionSystem:
    """Тесты для системы разрешений"""

    def test_admin_permissions(self, db_session, admin_user_with_roles, test_community):
        """Тест разрешений администратора"""
        from auth.permissions import ContextualPermissionCheck

        # Проверяем что администратор имеет все разрешения
        permissions_to_check = [
            "shout:read", "shout:create", "shout:update", "shout:delete",
            "topic:create", "topic:update", "topic:delete",
            "user:manage", "community:manage"
        ]

        for permission in permissions_to_check:
            resource, operation = permission.split(":")
            has_permission = ContextualPermissionCheck.check_permission(
                db_session,
                admin_user_with_roles.id,
                test_community.slug,
                resource,
                operation
            )
            # Администратор должен иметь все разрешения
            assert has_permission is True

    def test_regular_user_permissions(self, db_session, regular_user_with_roles, test_community):
        """Тест разрешений обычного пользователя"""
        from auth.permissions import ContextualPermissionCheck

        # Проверяем что обычный пользователь имеет роли reader и author
        ca = CommunityAuthor.find_author_in_community(
            regular_user_with_roles.id,
            test_community.id,
            db_session
        )
        assert ca is not None
        assert ca.has_role("reader")
        assert ca.has_role("author")

        # Проверяем что пользователь не имеет админских ролей
        assert not ca.has_role("admin")

    def test_permission_without_community_author(self, db_session, test_users, test_community):
        """Тест разрешений для пользователя без CommunityAuthor"""
        from auth.permissions import ContextualPermissionCheck

        # Проверяем разрешения для пользователя без ролей в сообществе
        has_permission = ContextualPermissionCheck.check_permission(
            db_session,
            test_users[2].id,  # Пользователь без ролей
            test_community.slug,
            "shout",
            "read"
        )

        # Пользователь без ролей не должен иметь разрешений
        assert has_permission is False


class TestEdgeCases:
    """Тесты краевых случаев"""

    def test_user_with_none_roles(self, db_session, test_users, test_community):
        """Тест пользователя с None ролями"""
        user = test_users[0]

        # Создаем CommunityAuthor с None ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles=None
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что None роли обрабатываются корректно
        assert ca.role_list == []
        assert not ca.has_role("reader")

    def test_user_with_whitespace_roles(self, db_session, test_users, test_community):
        """Тест пользователя с ролями содержащими пробелы"""
        user = test_users[0]

        # Создаем CommunityAuthor с ролями содержащими пробелы
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="reader, author, expert"
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что пробелы корректно обрабатываются
        assert set(ca.role_list) == {"reader", "author", "expert"}

    def test_community_with_deleted_creator(self, db_session, test_users):
        """Тест сообщества с удаленным создателем"""
        # Создаем пользователя
        user = test_users[0]

        # Создаем сообщество с создателем
        community = Community(
            id=300,
            name="Community with Creator",
            slug="community-with-creator",
            desc="Test community with creator",
            created_by=user.id,
            created_at=int(time.time())
        )
        db_session.add(community)
        db_session.commit()

        # Удаляем создателя
        db_session.delete(user)
        db_session.commit()

        # Проверяем что сообщество остается с ID создателя
        updated_community = db_session.query(Community).where(Community.id == 300).first()
        assert updated_community.created_by == user.id  # ID остается, но пользователь удален


class TestIntegration:
    """Интеграционные тесты"""

    def test_full_admin_workflow(self, db_session, test_users, test_community):
        """Полный тест рабочего процесса админ-панели"""
        user = test_users[0]

        # 1. Создаем пользователя с ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="admin,editor"
        )
        db_session.add(ca)
        db_session.commit()

        # 2. Проверяем роли
        assert ca.has_role("admin")
        assert ca.has_role("editor")

        # 3. Добавляем новую роль
        ca.add_role("author")
        db_session.commit()
        assert ca.has_role("author")

        # 4. Удаляем роль
        ca.remove_role("editor")
        db_session.commit()
        assert not ca.has_role("editor")
        assert ca.has_role("admin")
        assert ca.has_role("author")

        # 5. Устанавливаем новые роли
        ca.set_roles(["reader", "expert"])
        db_session.commit()
        assert ca.has_role("reader")
        assert ca.has_role("expert")
        assert not ca.has_role("admin")
        assert not ca.has_role("author")

    def test_multiple_users_admin_management(self, db_session, test_users, test_community):
        """Тест управления несколькими пользователями"""
        # Создаем CommunityAuthor для всех пользователей
        for i, user in enumerate(test_users):
            roles = ["reader"]
            if i == 0:
                roles.append("admin")
            elif i == 1:
                roles.append("editor")

            ca = CommunityAuthor(
                community_id=test_community.id,
                author_id=user.id,
                roles=",".join(roles)
            )
            db_session.add(ca)

        db_session.commit()

        # Проверяем роли каждого пользователя
        for i, user in enumerate(test_users):
            ca = CommunityAuthor.find_author_in_community(
                user.id,
                test_community.id,
                db_session
            )
            assert ca is not None

            if i == 0:
                assert ca.has_role("admin")
            elif i == 1:
                assert ca.has_role("editor")

            assert ca.has_role("reader")
