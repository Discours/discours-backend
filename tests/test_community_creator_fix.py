"""
Тесты для исправлений системы обработки сообществ без создателя.

Проверяет работу с сообществами, у которых отсутствует создатель (created_by = None),
и корректность работы обновленных методов.
"""

import pytest
import time
from sqlalchemy.orm import Session

from auth.orm import Author
from orm.community import (
    Community,
    CommunityAuthor,
    CommunityFollower,
    get_user_roles_in_community,
    assign_role_to_user,
    remove_role_from_user
)
from services.db import local_session


# Используем общую фикстуру из conftest.py


# Используем общую фикстуру из conftest.py


@pytest.fixture
def community_with_creator(db_session, test_users):
    """Создает сообщество с создателем"""
    community = Community(
        id=101,
        name="Community With Creator",
        slug="community-with-creator",
        desc="Test community with creator",
        created_by=test_users[0].id,
        created_at=int(time.time())
    )
    db_session.add(community)
    db_session.commit()
    return community


class TestCommunityWithoutCreator:
    """Тесты для работы с сообществами без создателя"""

    def test_community_creation_without_creator(self, db_session, community_without_creator):
        """Тест создания сообщества без создателя"""
        assert community_without_creator.created_by is None
        assert community_without_creator.name == "Community Without Creator"
        assert community_without_creator.slug == "community-without-creator"

    def test_community_creation_with_creator(self, db_session, community_with_creator):
        """Тест создания сообщества с создателем"""
        assert community_with_creator.created_by is not None
        assert community_with_creator.created_by == 1  # ID первого пользователя

    def test_community_creator_assignment(self, db_session, community_without_creator, test_users):
        """Тест назначения создателя сообществу"""
        # Назначаем создателя
        community_without_creator.created_by = test_users[0].id
        db_session.commit()

        # Проверяем что создатель назначен
        assert community_without_creator.created_by == test_users[0].id

    def test_community_followers_without_creator(self, db_session, community_without_creator, test_users):
        """Тест работы с подписчиками сообщества без создателя"""
        # Добавляем подписчиков
        follower1 = CommunityFollower(
            community=community_without_creator.id,
            follower=test_users[0].id
        )
        follower2 = CommunityFollower(
            community=community_without_creator.id,
            follower=test_users[1].id
        )

        db_session.add(follower1)
        db_session.add(follower2)
        db_session.commit()

        # Проверяем что подписчики добавлены
        followers = db_session.query(CommunityFollower).where(
            CommunityFollower.community == community_without_creator.id
        ).all()

        assert len(followers) == 2
        follower_ids = [f.follower for f in followers]
        assert test_users[0].id in follower_ids
        assert test_users[1].id in follower_ids


class TestUpdatedMethods:
    """Тесты для обновленных методов"""

    def test_find_author_in_community_method(self, db_session, test_users, community_with_creator):
        """Тест обновленного метода find_author_in_community"""
        # Создаем запись CommunityAuthor
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles="reader,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Тестируем метод find_author_in_community
        result = CommunityAuthor.find_author_in_community(test_users[0].id, community_with_creator.id, db_session)
        assert result is not None
        assert result.author_id == test_users[0].id
        assert result.community_id == community_with_creator.id
        assert result.roles == "reader,author"

    def test_find_author_in_community_not_found(self, db_session, test_users, community_with_creator):
        """Тест метода find_author_in_community когда запись не найдена"""
        result = CommunityAuthor.find_author_in_community(999, community_with_creator.id, db_session)
        assert result is None

    def test_get_user_roles_in_community_without_creator(self, db_session, test_users, community_without_creator):
        """Тест получения ролей пользователя в сообществе без создателя"""
        # Создаем запись CommunityAuthor
        ca = CommunityAuthor(
            community_id=community_without_creator.id,
            author_id=test_users[0].id,
            roles="reader,expert"
        )
        db_session.add(ca)
        db_session.commit()

        # Получаем роли через CommunityAuthor напрямую
        ca_found = CommunityAuthor.find_author_in_community(test_users[0].id, community_without_creator.id, db_session)
        assert ca_found is not None
        roles = ca_found.role_list

        # Проверяем что роли получены корректно
        assert "reader" in roles
        assert "expert" in roles
        assert len(roles) == 2

    def test_assign_role_to_user_without_creator(self, db_session, test_users, community_without_creator):
        """Тест назначения роли пользователю в сообществе без создателя"""
        # Назначаем роль
        result = assign_role_to_user(test_users[0].id, "reader", community_without_creator.id)
        assert result is True

        # Проверяем что роль назначена
        roles = get_user_roles_in_community(test_users[0].id, community_without_creator.id)
        assert "reader" in roles

    def test_remove_role_from_user_without_creator(self, db_session, test_users, community_without_creator):
        """Тест удаления роли пользователя в сообществе без создателя"""
        # Сначала назначаем роль
        assign_role_to_user(test_users[0].id, "reader", community_without_creator.id)
        assign_role_to_user(test_users[0].id, "author", community_without_creator.id)

        # Удаляем одну роль
        result = remove_role_from_user(test_users[0].id, "reader", community_without_creator.id)
        assert result is True

        # Проверяем что роль удалена
        roles = get_user_roles_in_community(test_users[0].id, community_without_creator.id)
        assert "reader" not in roles
        assert "author" in roles


class TestCommunityAuthorMethods:
    """Тесты для методов CommunityAuthor"""

    def test_add_role_method(self, db_session, test_users, community_with_creator):
        """Тест метода add_role"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles="reader"
        )
        db_session.add(ca)
        db_session.commit()

        # Добавляем роль
        ca.add_role("author")
        db_session.commit()

        # Проверяем что роль добавлена
        assert ca.has_role("reader")
        assert ca.has_role("author")

    def test_remove_role_method(self, db_session, test_users, community_with_creator):
        """Тест метода remove_role"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles="reader,author,expert"
        )
        db_session.add(ca)
        db_session.commit()

        # Удаляем роль
        ca.remove_role("author")
        db_session.commit()

        # Проверяем что роль удалена
        assert ca.has_role("reader")
        assert not ca.has_role("author")
        assert ca.has_role("expert")

    def test_has_role_method(self, db_session, test_users, community_with_creator):
        """Тест метода has_role"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles="reader,author"
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем существующие роли
        assert ca.has_role("reader") is True
        assert ca.has_role("author") is True

        # Проверяем несуществующие роли
        assert ca.has_role("admin") is False
        assert ca.has_role("editor") is False

    def test_set_roles_method(self, db_session, test_users, community_with_creator):
        """Тест метода set_roles"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles="reader"
        )
        db_session.add(ca)
        db_session.commit()

        # Устанавливаем новые роли
        ca.set_roles(["admin", "editor"])
        db_session.commit()

        # Проверяем что роли установлены
        assert ca.roles == "admin,editor"
        assert ca.has_role("admin")
        assert ca.has_role("editor")
        assert not ca.has_role("reader")


class TestEdgeCases:
    """Тесты краевых случаев"""

    def test_empty_roles_string(self, db_session, test_users, community_with_creator):
        """Тест обработки пустой строки ролей"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles=""
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что пустые роли обрабатываются корректно
        assert ca.role_list == []
        assert not ca.has_role("reader")

    def test_none_roles(self, db_session, test_users, community_with_creator):
        """Тест обработки None ролей"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles=None
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что None роли обрабатываются корректно
        assert ca.role_list == []
        assert not ca.has_role("reader")

    def test_whitespace_in_roles(self, db_session, test_users, community_with_creator):
        """Тест обработки пробелов в ролях"""
        ca = CommunityAuthor(
            community_id=community_with_creator.id,
            author_id=test_users[0].id,
            roles=" reader , author , expert "
        )
        db_session.add(ca)
        db_session.commit()

        # Проверяем что пробелы корректно обрабатываются
        assert set(ca.role_list) == {"reader", "author", "expert"}


class TestIntegration:
    """Интеграционные тесты"""

    def test_full_workflow_without_creator(self, db_session, test_users, community_without_creator):
        """Полный тест рабочего процесса с сообществом без создателя"""
        # 1. Создаем CommunityAuthor
        ca = CommunityAuthor(
            community_id=community_without_creator.id,
            author_id=test_users[0].id,
            roles="reader"
        )
        db_session.add(ca)
        db_session.commit()

        # 2. Добавляем роли
        ca.add_role("author")
        ca.add_role("expert")
        db_session.commit()

        # 3. Проверяем роли
        assert ca.has_role("reader")
        assert ca.has_role("author")
        assert ca.has_role("expert")

        # 4. Удаляем роль
        ca.remove_role("author")
        db_session.commit()

        # 5. Проверяем результат
        assert ca.has_role("reader")
        assert not ca.has_role("author")
        assert ca.has_role("expert")

        # 6. Устанавливаем новые роли
        ca.set_roles(["admin", "editor"])
        db_session.commit()

        # 7. Финальная проверка
        assert ca.has_role("admin")
        assert ca.has_role("editor")
        assert not ca.has_role("reader")
        assert not ca.has_role("expert")

    def test_multiple_users_in_community_without_creator(self, db_session, test_users, community_without_creator):
        """Тест работы с несколькими пользователями в сообществе без создателя"""
        # Создаем записи для всех пользователей
        for i, user in enumerate(test_users):
            roles = ["reader"]
            if i == 0:
                roles.append("author")
            elif i == 1:
                roles.append("expert")

            ca = CommunityAuthor(
                community_id=community_without_creator.id,
                author_id=user.id,
                roles=",".join(roles)
            )
            db_session.add(ca)

        db_session.commit()

        # Проверяем роли каждого пользователя через CommunityAuthor напрямую
        user1_ca = CommunityAuthor.find_author_in_community(test_users[0].id, community_without_creator.id, db_session)
        user2_ca = CommunityAuthor.find_author_in_community(test_users[1].id, community_without_creator.id, db_session)
        user3_ca = CommunityAuthor.find_author_in_community(test_users[2].id, community_without_creator.id, db_session)

        user1_roles = user1_ca.role_list if user1_ca else []
        user2_roles = user2_ca.role_list if user2_ca else []
        user3_roles = user3_ca.role_list if user3_ca else []

        # Проверяем что роли назначены корректно
        assert "reader" in user1_roles
        assert "author" in user1_roles
        assert len(user1_roles) == 2

        assert "reader" in user2_roles
        assert "expert" in user2_roles
        assert len(user2_roles) == 2

        assert "reader" in user3_roles
        assert len(user3_roles) == 1
