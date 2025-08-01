"""
Тесты для функциональности кастомных ролей
"""

import pytest
import json
from services.redis import redis
from services.db import local_session
from orm.community import Community
from resolvers.admin import admin_create_custom_role, admin_delete_custom_role, admin_get_roles


class TestCustomRoles:
    """Тесты для кастомных ролей"""

    @pytest.mark.asyncio
    async def test_create_custom_role(self, session):
        """Тест создания кастомной роли"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community",
            slug="test-community",
            desc="Test community for custom roles",
            created_by=1,
            created_at=1234567890
        )
        session.add(community)
        session.flush()

        # Данные для создания роли
        role_data = {
            "id": "custom_moderator",
            "name": "Модератор",
            "description": "Кастомная роль модератора",
            "icon": "shield",
            "community_id": community.id
        }

        # Создаем роль
        result = await admin_create_custom_role(None, None, role_data)

        # Проверяем результат
        assert result["success"] is True
        assert result["role"]["id"] == "custom_moderator"
        assert result["role"]["name"] == "Модератор"
        assert result["role"]["description"] == "Кастомная роль модератора"

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
    async def test_create_duplicate_role(self, session):
        """Тест создания дублирующей роли"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community 2",
            slug="test-community-2",
            desc="Test community for duplicate roles",
            created_by=1,
            created_at=1234567890
        )
        session.add(community)
        session.flush()

        # Данные для создания роли
        role_data = {
            "id": "duplicate_role",
            "name": "Дублирующая роль",
            "description": "Тестовая роль",
            "community_id": community.id
        }

        # Создаем роль первый раз
        result1 = await admin_create_custom_role(None, None, role_data)
        assert result1["success"] is True

        # Пытаемся создать роль с тем же ID
        result2 = await admin_create_custom_role(None, None, role_data)
        assert result2["success"] is False
        assert "уже существует" in result2["error"]

    @pytest.mark.asyncio
    async def test_delete_custom_role(self, session):
        """Тест удаления кастомной роли"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community 3",
            slug="test-community-3",
            desc="Test community for role deletion",
            created_by=1,
            created_at=1234567890
        )
        session.add(community)
        session.flush()

        # Создаем роль
        role_data = {
            "id": "role_to_delete",
            "name": "Роль для удаления",
            "description": "Тестовая роль",
            "community_id": community.id
        }

        create_result = await admin_create_custom_role(None, None, role_data)
        assert create_result["success"] is True

        # Удаляем роль
        delete_result = await admin_delete_custom_role(None, None, "role_to_delete", community.id)
        assert delete_result["success"] is True

        # Проверяем, что роль удалена из Redis
        role_json = await redis.execute("HGET", f"community:custom_roles:{community.id}", "role_to_delete")
        assert role_json is None

    @pytest.mark.asyncio
    async def test_get_roles_with_custom(self, session):
        """Тест получения ролей с кастомными"""
        # Создаем тестовое сообщество
        community = Community(
            name="Test Community 4",
            slug="test-community-4",
            desc="Test community for role listing",
            created_by=1,
            created_at=1234567890
        )
        session.add(community)
        session.flush()

        # Создаем кастомную роль
        role_data = {
            "id": "test_custom_role",
            "name": "Тестовая кастомная роль",
            "description": "Описание тестовой роли",
            "community_id": community.id
        }

        await admin_create_custom_role(None, None, role_data)

        # Получаем роли для сообщества
        roles = await admin_get_roles(None, None, community.id)

        # Проверяем, что кастомная роль есть в списке
        custom_role = next((role for role in roles if role["id"] == "test_custom_role"), None)
        assert custom_role is not None
        assert custom_role["name"] == "Тестовая кастомная роль"
        assert custom_role["description"] == "Описание тестовой роли"

        # Проверяем, что базовые роли тоже есть
        base_role_ids = [role["id"] for role in roles]
        assert "reader" in base_role_ids
        assert "author" in base_role_ids
        assert "editor" in base_role_ids
        assert "admin" in base_role_ids
