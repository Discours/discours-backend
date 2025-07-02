"""
Админ-резолверы - тонкие GraphQL обёртки над AdminService
"""

from typing import Any

from graphql import GraphQLResolveInfo
from graphql.error import GraphQLError

from auth.decorators import admin_auth_required
from services.admin import admin_service
from services.schema import mutation, query
from utils.logger import root_logger as logger


def handle_error(operation: str, error: Exception) -> GraphQLError:
    """Обрабатывает ошибки в резолверах"""
    logger.error(f"Ошибка при {operation}: {error}")
    return GraphQLError(f"Не удалось {operation}: {error}")


# === ПОЛЬЗОВАТЕЛИ ===


@query.field("adminGetUsers")
@admin_auth_required
async def admin_get_users(
    _: None, _info: GraphQLResolveInfo, limit: int = 20, offset: int = 0, search: str = ""
) -> dict[str, Any]:
    """Получает список пользователей"""
    try:
        return admin_service.get_users(limit, offset, search)
    except Exception as e:
        raise handle_error("получении списка пользователей", e) from e


@mutation.field("adminUpdateUser")
@admin_auth_required
async def admin_update_user(_: None, _info: GraphQLResolveInfo, user: dict[str, Any]) -> dict[str, Any]:
    """Обновляет данные пользователя"""
    try:
        return admin_service.update_user(user)
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        return {"success": False, "error": str(e)}


# === ПУБЛИКАЦИИ ===


@query.field("adminGetShouts")
@admin_auth_required
async def admin_get_shouts(
    _: None,
    _info: GraphQLResolveInfo,
    limit: int = 20,
    offset: int = 0,
    search: str = "",
    status: str = "all",
    community: int = None,
) -> dict[str, Any]:
    """Получает список публикаций"""
    try:
        return admin_service.get_shouts(limit, offset, search, status, community)
    except Exception as e:
        raise handle_error("получении списка публикаций", e) from e


@mutation.field("adminUpdateShout")
@admin_auth_required
async def admin_update_shout(_: None, info: GraphQLResolveInfo, shout: dict[str, Any]) -> dict[str, Any]:
    """Обновляет публикацию через editor.py"""
    try:
        from resolvers.editor import update_shout

        shout_id = shout.get("id")
        if not shout_id:
            return {"success": False, "error": "ID публикации не указан"}

        shout_input = {k: v for k, v in shout.items() if k != "id"}
        result = await update_shout(None, info, shout_id, shout_input)

        if result.error:
            return {"success": False, "error": result.error}

        logger.info(f"Публикация {shout_id} обновлена через админ-панель")
        return {"success": True}
    except Exception as e:
        logger.error(f"Ошибка обновления публикации: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminDeleteShout")
@admin_auth_required
async def admin_delete_shout(_: None, info: GraphQLResolveInfo, shout_id: int) -> dict[str, Any]:
    """Удаляет публикацию через editor.py"""
    try:
        from resolvers.editor import delete_shout

        result = await delete_shout(None, info, shout_id)
        if result.error:
            return {"success": False, "error": result.error}

        logger.info(f"Публикация {shout_id} удалена через админ-панель")
        return {"success": True}
    except Exception as e:
        logger.error(f"Ошибка удаления публикации: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminRestoreShout")
@admin_auth_required
async def admin_restore_shout(_: None, _info: GraphQLResolveInfo, shout_id: int) -> dict[str, Any]:
    """Восстанавливает удаленную публикацию"""
    try:
        return admin_service.restore_shout(shout_id)
    except Exception as e:
        logger.error(f"Ошибка восстановления публикации: {e}")
        return {"success": False, "error": str(e)}


# === ПРИГЛАШЕНИЯ ===


@query.field("adminGetInvites")
@admin_auth_required
async def admin_get_invites(
    _: None, _info: GraphQLResolveInfo, limit: int = 20, offset: int = 0, search: str = "", status: str = "all"
) -> dict[str, Any]:
    """Получает список приглашений"""
    try:
        return admin_service.get_invites(limit, offset, search, status)
    except Exception as e:
        raise handle_error("получении списка приглашений", e) from e


@mutation.field("adminUpdateInvite")
@admin_auth_required
async def admin_update_invite(_: None, _info: GraphQLResolveInfo, invite: dict[str, Any]) -> dict[str, Any]:
    """Обновляет приглашение"""
    try:
        return admin_service.update_invite(invite)
    except Exception as e:
        logger.error(f"Ошибка обновления приглашения: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminDeleteInvite")
@admin_auth_required
async def admin_delete_invite(
    _: None, _info: GraphQLResolveInfo, inviter_id: int, author_id: int, shout_id: int
) -> dict[str, Any]:
    """Удаляет приглашение"""
    try:
        return admin_service.delete_invite(inviter_id, author_id, shout_id)
    except Exception as e:
        logger.error(f"Ошибка удаления приглашения: {e}")
        return {"success": False, "error": str(e)}


# === ТОПИКИ ===


@query.field("adminGetTopics")
@admin_auth_required
async def admin_get_topics(_: None, _info: GraphQLResolveInfo, community_id: int) -> list[dict[str, Any]]:
    """Получает все топики сообщества для админ-панели"""
    try:
        from orm.topic import Topic
        from services.db import local_session

        with local_session() as session:
            # Получаем все топики сообщества без лимитов
            topics = session.query(Topic).filter(Topic.community == community_id).order_by(Topic.id).all()

            # Сериализуем топики в простой формат для админки
            result: list[dict[str, Any]] = [
                {
                    "id": topic.id,
                    "title": topic.title or "",
                    "slug": topic.slug or f"topic-{topic.id}",
                    "body": topic.body or "",
                    "community": topic.community,
                    "parent_ids": topic.parent_ids or [],
                    "pic": topic.pic,
                    "oid": getattr(topic, "oid", None),
                    "is_main": getattr(topic, "is_main", False),
                }
                for topic in topics
            ]

            logger.info("Загружено топиков для сообщества", len(result))
            return result

    except Exception as e:
        raise handle_error("получении списка топиков", e) from e


# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===


@query.field("getEnvVariables")
@admin_auth_required
async def get_env_variables(_: None, _info: GraphQLResolveInfo) -> list[dict[str, Any]]:
    """Получает переменные окружения"""
    try:
        return await admin_service.get_env_variables()
    except Exception as e:
        logger.error("Ошибка получения переменных окружения", e)
        raise GraphQLError("Не удалось получить переменные окружения", e) from e


@mutation.field("updateEnvVariable")
@admin_auth_required
async def update_env_variable(_: None, _info: GraphQLResolveInfo, key: str, value: str) -> dict[str, Any]:
    """Обновляет переменную окружения"""
    return await admin_service.update_env_variable(key, value)


@mutation.field("updateEnvVariables")
@admin_auth_required
async def update_env_variables(_: None, _info: GraphQLResolveInfo, variables: list[dict[str, Any]]) -> dict[str, Any]:
    """Массовое обновление переменных окружения"""
    return await admin_service.update_env_variables(variables)


# === РОЛИ ===


@query.field("adminGetRoles")
@admin_auth_required
async def admin_get_roles(_: None, _info: GraphQLResolveInfo, community: int = None) -> list[dict[str, Any]]:
    """Получает список ролей"""
    try:
        return admin_service.get_roles(community)
    except Exception as e:
        logger.error("Ошибка получения ролей", e)
        raise GraphQLError("Не удалось получить роли", e) from e


# === ЗАГЛУШКИ ДЛЯ ОСТАЛЬНЫХ РЕЗОЛВЕРОВ ===
# [предположение] Эти резолверы пока оставляем как есть, но их тоже нужно будет упростить


@query.field("adminGetUserCommunityRoles")
@admin_auth_required
async def admin_get_user_community_roles(
    _: None, _info: GraphQLResolveInfo, author_id: int, community_id: int
) -> dict[str, Any]:
    """Получает роли пользователя в сообществе"""
    # [непроверенное] Временная заглушка - нужно вынести в сервис
    from orm.community import CommunityAuthor
    from services.db import local_session

    try:
        with local_session() as session:
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
                .first()
            )

            roles = []
            if community_author and community_author.roles:
                roles = [role.strip() for role in community_author.roles.split(",") if role.strip()]

            return {"author_id": author_id, "community_id": community_id, "roles": roles}
    except Exception as e:
        raise handle_error("получении ролей пользователя в сообществе", e) from e


@query.field("adminGetCommunityMembers")
@admin_auth_required
async def admin_get_community_members(
    _: None, _info: GraphQLResolveInfo, community_id: int, limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    """Получает участников сообщества"""
    # [непроверенное] Временная заглушка - нужно вынести в сервис
    from sqlalchemy.sql import func

    from auth.orm import Author
    from orm.community import CommunityAuthor
    from services.db import local_session

    try:
        with local_session() as session:
            members_query = (
                session.query(Author, CommunityAuthor)
                .join(CommunityAuthor, Author.id == CommunityAuthor.author_id)
                .filter(CommunityAuthor.community_id == community_id)
                .offset(offset)
                .limit(limit)
            )

            members = []
            for author, community_author in members_query:
                roles = []
                if community_author.roles:
                    roles = [role.strip() for role in community_author.roles.split(",") if role.strip()]

                members.append(
                    {
                        "id": author.id,
                        "name": author.name,
                        "email": author.email,
                        "slug": author.slug,
                        "roles": roles,
                    }
                )

            total = (
                session.query(func.count(CommunityAuthor.author_id))
                .filter(CommunityAuthor.community_id == community_id)
                .scalar()
            )

            return {"members": members, "total": total, "community_id": community_id}
    except Exception as e:
        logger.error(f"Ошибка получения участников сообщества: {e}")
        return {"members": [], "total": 0, "community_id": community_id}


@query.field("adminGetCommunityRoleSettings")
@admin_auth_required
async def admin_get_community_role_settings(_: None, _info: GraphQLResolveInfo, community_id: int) -> dict[str, Any]:
    """Получает настройки ролей сообщества"""
    # [непроверенное] Временная заглушка - нужно вынести в сервис
    from orm.community import Community
    from services.db import local_session

    try:
        with local_session() as session:
            community = session.query(Community).filter(Community.id == community_id).first()
            if not community:
                return {
                    "community_id": community_id,
                    "default_roles": ["reader"],
                    "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"],
                    "error": "Сообщество не найдено",
                }

            return {
                "community_id": community_id,
                "default_roles": community.get_default_roles(),
                "available_roles": community.get_available_roles(),
                "error": None,
            }
    except Exception as e:
        logger.error(f"Ошибка получения настроек ролей: {e}")
        return {
            "community_id": community_id,
            "default_roles": ["reader"],
            "available_roles": ["reader", "author", "artist", "expert", "editor", "admin"],
            "error": str(e),
        }
