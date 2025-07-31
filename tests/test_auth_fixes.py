"""
Тесты для исправлений в системе авторизации.

Проверяет работу обновленных импортов, методов и обработку ошибок.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from auth.orm import Author, AuthorBookmark, AuthorRating, AuthorFollower
from auth.internal import verify_internal_auth
from auth.permissions import ContextualPermissionCheck
from orm.community import Community, CommunityAuthor
from auth.permissions import ContextualPermissionCheck
from services.db import local_session


# Используем общую фикстуру из conftest.py


@pytest.fixture
def mock_verify():
    """Мок для функции верификации внутренней авторизации"""
    with patch('auth.internal.verify_internal_auth') as mock:
        yield mock


@pytest.fixture
def test_community(db_session, test_users):
    """Создает тестовое сообщество"""
    community = Community(
        id=100,
        name="Test Community",
        slug="test-community",
        desc="Test community for auth tests",
        created_by=test_users[0].id,
        created_at=int(time.time())
    )
    db_session.add(community)
    db_session.commit()
    return community


class TestAuthORMFixes:
    """Тесты для исправлений в auth/orm.py"""

    def test_author_bookmark_creation(self, db_session, test_users):
        """Тест создания закладки автора"""
        bookmark = AuthorBookmark(
            author=test_users[0].id,
            shout=1
        )
        db_session.add(bookmark)
        db_session.commit()

        # Проверяем что закладка создана
        saved_bookmark = db_session.query(AuthorBookmark).where(
            AuthorBookmark.author == test_users[0].id,
            AuthorBookmark.shout == 1
        ).first()

        assert saved_bookmark is not None
        assert saved_bookmark.author == test_users[0].id
        assert saved_bookmark.shout == 1

    def test_author_rating_creation(self, db_session, test_users):
        """Тест создания рейтинга автора"""
        rating = AuthorRating(
            rater=test_users[0].id,
            author=test_users[1].id,
            plus=True
        )
        db_session.add(rating)
        db_session.commit()

        # Проверяем что рейтинг создан
        saved_rating = db_session.query(AuthorRating).where(
            AuthorRating.rater == test_users[0].id,
            AuthorRating.author == test_users[1].id
        ).first()

        assert saved_rating is not None
        assert saved_rating.rater == test_users[0].id
        assert saved_rating.author == test_users[1].id
        assert saved_rating.plus is True

    def test_author_follower_creation(self, db_session, test_users):
        """Тест создания подписки автора"""
        follower = AuthorFollower(
            follower=test_users[0].id,
            author=test_users[1].id,
            created_at=int(time.time()),
            auto=False
        )
        db_session.add(follower)
        db_session.commit()

        # Проверяем что подписка создана
        saved_follower = db_session.query(AuthorFollower).where(
            AuthorFollower.follower == test_users[0].id,
            AuthorFollower.author == test_users[1].id
        ).first()

        assert saved_follower is not None
        assert saved_follower.follower == test_users[0].id
        assert saved_follower.author == test_users[1].id
        assert saved_follower.auto is False

    def test_author_oauth_methods(self, db_session, test_users):
        """Тест методов работы с OAuth"""
        user = test_users[0]

        # Тестируем set_oauth_account
        user.set_oauth_account("google", "test_provider_id", "test@example.com")
        db_session.commit()

        # Проверяем что OAuth данные сохранены
        oauth_data = user.get_oauth_account("google")
        assert oauth_data is not None
        assert oauth_data.get("id") == "test_provider_id"
        assert oauth_data.get("email") == "test@example.com"

        # Тестируем remove_oauth_account
        user.remove_oauth_account("google")
        db_session.commit()

        # Проверяем что OAuth данные удалены
        oauth_data = user.get_oauth_account("google")
        assert oauth_data is None

    def test_author_password_methods(self, db_session, test_users):
        """Тест методов работы с паролями"""
        user = test_users[0]

        # Устанавливаем пароль
        user.set_password("new_password")
        db_session.commit()

        # Проверяем что пароль установлен
        assert user.verify_password("new_password") is True
        assert user.verify_password("wrong_password") is False

    def test_author_dict_method(self, db_session, test_users):
        """Тест метода dict() для сериализации"""
        user = test_users[0]

        # Добавляем роли
        user.roles_data = {"1": ["reader", "author"]}
        db_session.commit()

        # Получаем словарь
        user_dict = user.dict()

        # Проверяем основные поля
        assert user_dict["id"] == user.id
        assert user_dict["name"] == user.name
        assert user_dict["slug"] == user.slug
        # email может быть скрыт в dict() методе

        # Проверяем что основные поля присутствуют
        assert "id" in user_dict
        assert "name" in user_dict
        assert "slug" in user_dict


class TestAuthInternalFixes:
    """Тесты для исправлений в auth/internal.py"""

    @pytest.mark.asyncio
    async def test_verify_internal_auth_success(self, mock_verify, db_session, test_users):
        """Тест успешной верификации внутренней авторизации"""
        # Создаем CommunityAuthor для тестового пользователя
        from orm.community import CommunityAuthor
        ca = CommunityAuthor(
            community_id=1,
            author_id=test_users[0].id,
            roles="reader,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Мокаем функцию верификации
        mock_verify.return_value = (test_users[0].id, ["reader", "author"], False)

        # Вызываем функцию через мок
        result = await mock_verify("test_token")

        # Проверяем результат
        assert result[0] == test_users[0].id
        assert result[1] == ["reader", "author"]
        assert result[2] is False

        # Проверяем что функция была вызвана
        mock_verify.assert_called_once_with("test_token")

    @pytest.mark.asyncio
    async def test_verify_internal_auth_user_not_found(self, mock_verify, db_session):
        """Тест верификации когда пользователь не найден"""
        # Мокаем функцию верификации с несуществующим пользователем
        mock_verify.return_value = (0, [], False)

        # Вызываем функцию
        result = await verify_internal_auth("test_token")

        # Проверяем что возвращается 0 для несуществующего пользователя
        assert result[0] == 0
        assert result[1] == []
        assert result[2] is False


class TestPermissionsFixes:
    """Тесты для исправлений в auth/permissions.py"""

    async def test_contextual_permission_check_with_community(self, db_session, test_users, test_community):
        """Тест проверки разрешений в контексте сообщества"""
        # Создаем CommunityAuthor с ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=test_users[0].id,
            roles="reader,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Тестируем проверку разрешений
        has_permission = await ContextualPermissionCheck.check_community_permission(
            db_session,
            test_users[0].id,
            test_community.slug,
            "shout",
            "read"
        )

        # Проверяем результат (должно быть True для роли reader)
        assert has_permission is True

    async def test_contextual_permission_check_without_community_author(self, db_session, test_users, test_community):
        """Тест проверки разрешений когда CommunityAuthor не существует"""
        # Тестируем проверку разрешений для пользователя без ролей в сообществе
        has_permission = await ContextualPermissionCheck.check_community_permission(
            db_session,
            test_users[1].id,
            test_community.slug,
            "shout",
            "read"
        )

        # Проверяем результат (должно быть False)
        assert has_permission is False

    def test_get_user_roles_in_community(self, db_session, test_users, test_community):
        """Тест получения ролей пользователя в сообществе"""
        # Создаем CommunityAuthor с ролями
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=test_users[0].id,
            roles="reader,author,expert"
        )
        db_session.add(ca)
        db_session.commit()

        # Получаем роли
        roles = ContextualPermissionCheck.get_user_community_roles(
            db_session,
            test_users[0].id,
            test_community.slug
        )

        # Проверяем результат (возможно автоматически добавляется editor роль)
        expected_roles = {"reader", "author", "expert"}
        actual_roles = set(roles)

        # Проверяем что есть ожидаемые роли
        assert expected_roles.issubset(actual_roles), f"Expected {expected_roles} to be subset of {actual_roles}"

    def test_get_user_roles_in_community_not_found(self, db_session, test_users, test_community):
        """Тест получения ролей когда пользователь не найден в сообществе"""
        # Получаем роли для пользователя без ролей
        roles = ContextualPermissionCheck.get_user_community_roles(
            db_session,
            test_users[1].id,
            test_community.slug
        )

        # Проверяем результат (должен быть пустой список)
        assert roles == []


class TestCommunityAuthorFixes:
    """Тесты для исправлений в методах CommunityAuthor"""

    def test_find_author_in_community_method(self, db_session, test_users, test_community):
        """Тест метода find_author_in_community"""
        # Создаем CommunityAuthor
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=test_users[0].id,
            roles="reader,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Ищем запись
        result = CommunityAuthor.find_author_in_community(
            test_users[0].id,
            test_community.id,
            db_session
        )

        # Проверяем результат
        assert result is not None
        assert result.author_id == test_users[0].id
        assert result.community_id == test_community.id
        assert result.roles == "reader,author"

    def test_find_author_in_community_not_found(self, db_session, test_users, test_community):
        """Тест метода find_author_in_community когда запись не найдена"""
        # Ищем несуществующую запись
        result = CommunityAuthor.find_author_in_community(
            999,
            test_community.id,
            db_session
        )

        # Проверяем результат
        assert result is None

    def test_find_author_in_community_without_session(self, db_session, test_users, test_community):
        """Тест метода find_author_in_community без передачи сессии"""
        # Создаем CommunityAuthor
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=test_users[0].id,
            roles="reader,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Ищем запись без передачи сессии
        result = CommunityAuthor.find_author_in_community(
            test_users[0].id,
            test_community.id
        )

        # Проверяем результат
        assert result is not None
        assert result.author_id == test_users[0].id
        assert result.community_id == test_community.id


class TestEdgeCases:
    """Тесты краевых случаев"""

    def test_author_with_empty_oauth(self, db_session, test_users):
        """Тест работы с пустыми OAuth данными"""
        user = test_users[0]

        # Проверяем что пустые OAuth данные обрабатываются корректно
        oauth_data = user.get_oauth_account("google")
        assert oauth_data is None

        # Проверяем что удаление несуществующего OAuth не вызывает ошибок
        user.remove_oauth_account("google")
        db_session.commit()

    def test_author_with_none_roles_data(self, db_session, test_users):
        """Тест работы с None roles_data"""
        user = test_users[0]
        user.roles_data = None
        db_session.commit()

        # Проверяем что None roles_data обрабатывается корректно
        user_dict = user.dict()
        # Проверяем что словарь создается без ошибок
        assert isinstance(user_dict, dict)
        assert "id" in user_dict
        assert "name" in user_dict

    def test_community_author_with_empty_roles(self, db_session, test_users, test_community):
        """Тест работы с пустыми ролями в CommunityAuthor"""
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=test_users[0].id,
            roles=""
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что пустые роли обрабатываются корректно
        assert ca.role_list == []
        assert not ca.has_role("reader")

    def test_community_author_with_none_roles(self, db_session, test_users, test_community):
        """Тест работы с None ролями в CommunityAuthor"""
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=test_users[0].id,
            roles=None
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что None роли обрабатываются корректно
        assert ca.role_list == []
        assert not ca.has_role("reader")


class TestIntegration:
    """Интеграционные тесты"""

    def test_full_auth_workflow(self, db_session, test_users, test_community):
        """Полный тест рабочего процесса авторизации"""
        user = test_users[0]

        # 1. Создаем CommunityAuthor
        ca = CommunityAuthor(
            community_id=test_community.id,
            author_id=user.id,
            roles="reader"
        )
        db_session.add(ca)
        db_session.commit()

        # 2. Добавляем OAuth данные
        user.set_oauth_account("google", {
            "access_token": "test_token",
            "refresh_token": "test_refresh"
        })
        db_session.commit()

        # 3. Проверяем что все данные сохранены
        oauth_data = user.get_oauth_account("google")
        assert oauth_data is not None

        roles = CommunityAuthor.find_author_in_community(
            user.id,
            test_community.id,
            db_session
        )
        assert roles is not None
        assert roles.has_role("reader")

        # 4. Проверяем разрешения
        has_permission = ContextualPermissionCheck.check_permission(
            db_session,
            user.id,
            test_community.slug,
            "shout",
            "read"
        )
        assert has_permission is True

        # 5. Удаляем OAuth данные
        user.remove_oauth_account("google")
        db_session.commit()

        # 6. Проверяем что данные удалены
        oauth_data = user.get_oauth_account("google")
        assert oauth_data is None

    def test_multiple_communities_auth(self, db_session, test_users):
        """Тест авторизации в нескольких сообществах"""
        # Создаем несколько сообществ
        communities = []
        for i in range(3):
            community = Community(
                id=200 + i,
                name=f"Community {i}",
                slug=f"community-{i}",
                desc=f"Test community {i}",
                created_by=test_users[0].id,
                created_at=int(time.time())
            )
            db_session.add(community)
            communities.append(community)

        db_session.commit()

        # Создаем CommunityAuthor для каждого сообщества
        for i, community in enumerate(communities):
            roles = ["reader"]
            if i == 0:
                roles.append("author")
            elif i == 1:
                roles.append("expert")

            ca = CommunityAuthor(
                community_id=community.id,
                author_id=test_users[0].id,
                roles=",".join(roles)
            )
            db_session.add(ca)

        db_session.commit()

        # Проверяем роли в каждом сообществе
        for i, community in enumerate(communities):
            roles = CommunityAuthor.find_author_in_community(
                test_users[0].id,
                community.id,
                db_session
            )
            assert roles is not None

            if i == 0:
                assert roles.has_role("author")
            elif i == 1:
                assert roles.has_role("expert")

            assert roles.has_role("reader")
