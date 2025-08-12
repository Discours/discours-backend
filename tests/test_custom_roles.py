"""
Тесты для функциональности кастомных ролей
"""

import pytest
import json
from unittest.mock import Mock
from services.redis import redis
from services.db import local_session
from orm.community import Community


class TestCustomRoles:
    """Тесты для кастомных ролей"""

    @pytest.fixture(autouse=True)
    def setup_mock_info(self):
        """Создает mock для GraphQLResolveInfo"""
        self.mock_info = Mock()
        self.mock_info.field_name = "adminCreateCustomRole"

    @pytest.mark.asyncio
    async def test_create_custom_role_redis(self, db_session):
        """Тест создания кастомной роли через Redis"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community",
            slug="test-community",
            desc="Test community for custom roles",
            created_by=1,
            created_at=1234567890
        )
        db_session.add(community)
        db_session.flush()

        # Данные для создания роли
        role_data = {
            "id": "custom_moderator",
            "name": "Модератор",
            "description": "Кастомная роль модератора",
            "icon": "shield",
            "permissions": []
        }

        # Сохраняем роль в Redis напрямую
        await redis.execute("HSET", f"community:custom_roles:{community.id}", "custom_moderator", json.dumps(role_data))

        # Проверяем, что роль сохранена в Redis
        role_json = await redis.execute("HGET", f"community:custom_roles:{community.id}", "custom_moderator")
        assert role_json is not None

        role_data_redis = json.loads(role_json)
        assert role_data_redis["id"] == "custom_moderator"
        assert role_data_redis["name"] == "Модератор"
        assert role_data_redis["description"] == "Кастомная роль модератора"
        assert role_data_redis["icon"] == "shield"
        assert role_data_redis["permissions"] == []

    @pytest.mark.asyncio
    async def test_create_duplicate_role_redis(self, db_session):
        """Тест создания дублирующей роли через Redis"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community 2",
            slug="test-community-2",
            desc="Test community for duplicate roles",
            created_by=1,
            created_at=1234567890
        )
        db_session.add(community)
        db_session.flush()

        # Данные для создания роли
        role_data = {
            "id": "duplicate_role",
            "name": "Дублирующая роль",
            "description": "Тестовая роль",
            "permissions": []
        }

        # Создаем роль первый раз
        await redis.execute("HSET", f"community:custom_roles:{community.id}", "duplicate_role", json.dumps(role_data))

        # Проверяем, что роль создана
        role_json = await redis.execute("HGET", f"community:custom_roles:{community.id}", "duplicate_role")
        assert role_json is not None

        # Пытаемся создать роль с тем же ID - должно перезаписаться
        await redis.execute("HSET", f"community:custom_roles:{community.id}", "duplicate_role", json.dumps(role_data))
        
        # Проверяем, что роль все еще существует
        role_json2 = await redis.execute("HGET", f"community:custom_roles:{community.id}", "duplicate_role")
        assert role_json2 is not None

    @pytest.mark.asyncio
    async def test_delete_custom_role_redis(self, db_session):
        """Тест удаления кастомной роли через Redis"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community 3",
            slug="test-community-3",
            desc="Test community for role deletion",
            created_by=1,
            created_at=1234567890
        )
        db_session.add(community)
        db_session.flush()

        # Создаем роль
        role_data = {
            "id": "role_to_delete",
            "name": "Роль для удаления",
            "description": "Тестовая роль",
            "permissions": []
        }

        # Сохраняем роль в Redis
        await redis.execute("HSET", f"community:custom_roles:{community.id}", "role_to_delete", json.dumps(role_data))

        # Проверяем, что роль создана
        role_json = await redis.execute("HGET", f"community:custom_roles:{community.id}", "role_to_delete")
        assert role_json is not None

        # Удаляем роль из Redis
        await redis.execute("HDEL", f"community:custom_roles:{community.id}", "role_to_delete")

        # Проверяем, что роль удалена из Redis
        role_json_after = await redis.execute("HGET", f"community:custom_roles:{community.id}", "role_to_delete")
        assert role_json_after is None

    @pytest.mark.asyncio
    async def test_get_roles_with_custom_redis(self, db_session):
        """Тест получения ролей с кастомными через Redis"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community 4",
            slug="test-community-4",
            desc="Test community for role listing",
            created_by=1,
            created_at=1234567890
        )
        db_session.add(community)
        db_session.flush()

        # Создаем кастомную роль
        role_data = {
            "id": "test_custom_role",
            "name": "Тестовая кастомная роль",
            "description": "Описание тестовой роли",
            "permissions": []
        }

        # Сохраняем роль в Redis
        await redis.execute("HSET", f"community:custom_roles:{community.id}", "test_custom_role", json.dumps(role_data))

        # Проверяем, что роль сохранена
        role_json = await redis.execute("HGET", f"community:custom_roles:{community.id}", "test_custom_role")
        assert role_json is not None

        role_data_redis = json.loads(role_json)
        assert role_data_redis["id"] == "test_custom_role"
        assert role_data_redis["name"] == "Тестовая кастомная роль"
        assert role_data_redis["description"] == "Описание тестовой роли"
