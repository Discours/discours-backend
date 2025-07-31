"""
Админ-резолверы - тонкие GraphQL обёртки над AdminService
"""

import time
from typing import Any, Optional

from graphql import GraphQLError, GraphQLResolveInfo
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import aliased

from auth.decorators import admin_auth_required
from auth.orm import Author
from orm.community import Community, CommunityAuthor
from orm.draft import DraftTopic
from orm.reaction import Reaction
from orm.shout import Shout, ShoutTopic
from orm.topic import Topic, TopicFollower
from resolvers.editor import delete_shout, update_shout
from resolvers.topic import invalidate_topic_followers_cache, invalidate_topics_cache
from services.admin import AdminService
from services.common_result import handle_error
from services.db import local_session
from services.redis import redis
from services.schema import mutation, query
from utils.logger import root_logger as logger

admin_service = AdminService()


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
    limit: int = 10,
    offset: int = 0,
    search: str = "",
    status: str = "all",
    community: Optional[int] = None,
) -> dict[str, Any]:
    """Получает список публикаций"""
    try:
        return await admin_service.get_shouts(limit, offset, search, status, community)
    except Exception as e:
        raise handle_error("получении списка публикаций", e) from e


@mutation.field("adminUpdateShout")
@admin_auth_required
async def admin_update_shout(_: None, info: GraphQLResolveInfo, shout: dict[str, Any]) -> dict[str, Any]:
    """Обновляет публикацию через editor.py"""
    try:
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
async def admin_get_topics(_: None, _info: GraphQLResolveInfo, community_id: int) -> list[Topic]:
    with local_session() as session:
        return session.query(Topic).where(Topic.community == community_id).all()


@mutation.field("adminUpdateTopic")
@admin_auth_required
async def admin_update_topic(_: None, _info: GraphQLResolveInfo, topic: dict[str, Any]) -> dict[str, Any]:
    """Обновляет топик через админ-панель"""
    try:
        topic_id = topic.get("id")
        if not topic_id:
            return {"success": False, "error": "ID топика не указан"}

        with local_session() as session:
            existing_topic = session.query(Topic).where(Topic.id == topic_id).first()
            if not existing_topic:
                return {"success": False, "error": "Топик не найден"}

            # Сохраняем старый slug для удаления из кеша
            old_slug = str(getattr(existing_topic, "slug", ""))

            # Обновляем поля топика
            for key, value in topic.items():
                if key != "id" and hasattr(existing_topic, key):
                    setattr(existing_topic, key, value)

            session.add(existing_topic)
            session.commit()

            # Инвалидируем кеш
            await invalidate_topics_cache(topic_id)

            # Если slug изменился, удаляем старый ключ
            new_slug = str(getattr(existing_topic, "slug", ""))
            if old_slug != new_slug:
                await redis.execute("DEL", f"topic:slug:{old_slug}")
                logger.debug(f"Удален ключ кеша для старого slug: {old_slug}")

            logger.info(f"Топик {topic_id} обновлен через админ-панель")
            return {"success": True, "topic": existing_topic}

    except Exception as e:
        logger.error(f"Ошибка обновления топика: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminCreateTopic")
@admin_auth_required
async def admin_create_topic(_: None, _info: GraphQLResolveInfo, topic: dict[str, Any]) -> dict[str, Any]:
    """Создает новый топик через админ-панель"""
    try:
        with local_session() as session:
            # Создаем новый топик
            new_topic = Topic(**topic)
            session.add(new_topic)
            session.commit()

            # Инвалидируем кеш всех тем
            await invalidate_topics_cache()

            logger.info(f"Топик {new_topic.id} создан через админ-панель")
            return {"success": True, "topic": new_topic}

    except Exception as e:
        logger.error(f"Ошибка создания топика: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminMergeTopics")
@admin_auth_required
async def admin_merge_topics(_: None, _info: GraphQLResolveInfo, merge_input: dict[str, Any]) -> dict[str, Any]:
    """
    Административное слияние топиков с переносом всех публикаций и подписчиков

    Args:
        merge_input: Данные для слияния:
            - target_topic_id: ID целевой темы (в которую сливаем)
            - source_topic_ids: Список ID исходных тем (которые сливаем)
            - preserve_target_properties: Сохранить свойства целевой темы

    Returns:
        dict: Результат операции с информацией о слиянии
    """
    try:
        target_topic_id = merge_input["target_topic_id"]
        source_topic_ids = merge_input["source_topic_ids"]
        preserve_target = merge_input.get("preserve_target_properties", True)

        # Проверяем что ID не пересекаются
        if target_topic_id in source_topic_ids:
            return {"success": False, "error": "Целевая тема не может быть в списке исходных тем"}

        with local_session() as session:
            # Получаем целевую тему
            target_topic = session.query(Topic).where(Topic.id == target_topic_id).first()
            if not target_topic:
                return {"success": False, "error": f"Целевая тема с ID {target_topic_id} не найдена"}

            # Получаем исходные темы
            source_topics = session.query(Topic).where(Topic.id.in_(source_topic_ids)).all()
            if len(source_topics) != len(source_topic_ids):
                found_ids = [t.id for t in source_topics]
                missing_ids = [topic_id for topic_id in source_topic_ids if topic_id not in found_ids]
                return {"success": False, "error": f"Исходные темы с ID {missing_ids} не найдены"}

            # Проверяем что все темы принадлежат одному сообществу
            target_community = target_topic.community
            for source_topic in source_topics:
                if source_topic.community != target_community:
                    return {"success": False, "error": f"Тема '{source_topic.title}' принадлежит другому сообществу"}

            # Собираем статистику для отчета
            merge_stats = {"followers_moved": 0, "publications_moved": 0, "drafts_moved": 0, "source_topics_deleted": 0}

            # Переносим подписчиков из исходных тем в целевую
            for source_topic in source_topics:
                # Получаем подписчиков исходной темы
                source_followers = session.query(TopicFollower).where(TopicFollower.topic == source_topic.id).all()

                for follower in source_followers:
                    # Проверяем, не подписан ли уже пользователь на целевую тему
                    existing = (
                        session.query(TopicFollower)
                        .where(TopicFollower.topic == target_topic_id, TopicFollower.follower == follower.follower)
                        .first()
                    )

                    if not existing:
                        # Создаем новую подписку на целевую тему
                        new_follower = TopicFollower(
                            topic=target_topic_id,
                            follower=follower.follower,
                            created_at=follower.created_at,
                            auto=follower.auto,
                        )
                        session.add(new_follower)
                        merge_stats["followers_moved"] += 1

                    # Удаляем старую подписку
                    session.delete(follower)

            # Переносим публикации из исходных тем в целевую
            for source_topic in source_topics:
                # Получаем связи публикаций с исходной темой
                shout_topics = session.query(ShoutTopic).where(ShoutTopic.topic == source_topic.id).all()

                for shout_topic in shout_topics:
                    # Проверяем, не связана ли уже публикация с целевой темой
                    existing_shout_topic: ShoutTopic | None = (
                        session.query(ShoutTopic)
                        .where(ShoutTopic.topic == target_topic_id)
                        .where(ShoutTopic.shout == shout_topic.shout)
                        .first()
                    )

                    if not existing_shout_topic:
                        # Создаем новую связь с целевой темой
                        new_shout_topic = ShoutTopic(
                            topic=target_topic_id, shout=shout_topic.shout, main=shout_topic.main
                        )
                        session.add(new_shout_topic)
                        merge_stats["publications_moved"] += 1

                    # Удаляем старую связь
                    session.delete(shout_topic)

            # Переносим черновики из исходных тем в целевую
            for source_topic in source_topics:
                # Получаем связи черновиков с исходной темой
                draft_topics = session.query(DraftTopic).where(DraftTopic.topic == source_topic.id).all()

                for draft_topic in draft_topics:
                    # Проверяем, не связан ли уже черновик с целевой темой
                    existing_draft_topic: DraftTopic | None = (
                        session.query(DraftTopic)
                        .where(DraftTopic.topic == target_topic_id)
                        .where(DraftTopic.draft == draft_topic.draft)
                        .first()
                    )

                    if not existing_draft_topic:
                        # Создаем новую связь с целевой темой
                        new_draft_topic = DraftTopic(
                            topic=target_topic_id, draft=draft_topic.draft, main=draft_topic.main
                        )
                        session.add(new_draft_topic)
                        merge_stats["drafts_moved"] += 1

                    # Удаляем старую связь
                    session.delete(draft_topic)

            # Обновляем parent_ids дочерних топиков
            for source_topic in source_topics:
                # Находим всех детей исходной темы
                child_topics = session.query(Topic).where(Topic.parent_ids.contains(int(source_topic.id))).all()  # type: ignore[arg-type]

                for child_topic in child_topics:
                    current_parent_ids = list(child_topic.parent_ids or [])
                    # Заменяем ID исходной темы на ID целевой темы
                    updated_parent_ids = [
                        target_topic_id if parent_id == source_topic.id else parent_id
                        for parent_id in current_parent_ids
                    ]
                    child_topic.parent_ids = list(updated_parent_ids)

            # Объединяем parent_ids если не сохраняем только целевые свойства
            if not preserve_target:
                current_parent_ids = list(target_topic.parent_ids or [])
                all_parent_ids = set(current_parent_ids)
                for source_topic in source_topics:
                    source_parent_ids = list(source_topic.parent_ids or [])
                    if source_parent_ids:
                        all_parent_ids.update(source_parent_ids)
                # Убираем IDs исходных тем из parent_ids
                all_parent_ids.discard(target_topic_id)
                for source_id in source_topic_ids:
                    all_parent_ids.discard(source_id)
                target_topic.parent_ids = list(all_parent_ids) if all_parent_ids else None

            # Инвалидируем кеши ПЕРЕД удалением тем
            for source_topic in source_topics:
                await invalidate_topic_followers_cache(int(source_topic.id))
                if source_topic.slug:
                    await redis.execute("DEL", f"topic:slug:{source_topic.slug}")
                await redis.execute("DEL", f"topic:id:{source_topic.id}")

            # Удаляем исходные темы
            for source_topic in source_topics:
                session.delete(source_topic)
                merge_stats["source_topics_deleted"] += 1
                logger.info(f"Удалена исходная тема: {source_topic.title} (ID: {source_topic.id})")

            # Сохраняем изменения
            session.commit()

            # Инвалидируем кеши целевой темы и общие кеши
            await invalidate_topics_cache(target_topic_id)
            await invalidate_topic_followers_cache(target_topic_id)

            logger.info(f"Успешно слиты темы {source_topic_ids} в тему {target_topic_id} через админ-панель")
            logger.info(f"Статистика слияния: {merge_stats}")

            return {
                "success": True,
                "topic": target_topic,
                "message": f"Успешно слито {len(source_topics)} тем в '{target_topic.title}'",
                "stats": merge_stats,
            }

    except Exception as e:
        logger.error(f"Ошибка при слиянии тем через админ-панель: {e}")
        return {"success": False, "error": f"Ошибка при слиянии тем: {e}"}


# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===


@query.field("getEnvVariables")
@admin_auth_required
async def get_env_variables(_: None, _info: GraphQLResolveInfo) -> list[dict[str, Any]]:
    """Получает переменные окружения"""
    try:
        return await admin_service.get_env_variables()
    except Exception as e:
        logger.error(f"Ошибка получения переменных окружения: {e}")
        raise GraphQLError("Не удалось получить переменные окружения") from e


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
async def admin_get_roles(_: None, _info: GraphQLResolveInfo, community: int | None = None) -> list[dict[str, Any]]:
    """Получает список ролей"""
    try:
        # Получаем все роли (базовые + кастомные)
        all_roles = admin_service.get_roles(community)

        # Если указано сообщество, добавляем кастомные роли из Redis
        if community:
            import json

            custom_roles_data = await redis.execute("HGETALL", f"community:custom_roles:{community}")

            for role_id, role_json in custom_roles_data.items():
                try:
                    role_data = json.loads(role_json)
                    all_roles.append(
                        {
                            "id": role_data["id"],
                            "name": role_data["name"],
                            "description": role_data.get("description", ""),
                        }
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Ошибка парсинга роли {role_id}: {e}")
                    continue

        return all_roles
    except Exception as e:
        logger.error(f"Ошибка получения ролей: {e}")
        raise GraphQLError("Не удалось получить роли") from e


# === ЗАГЛУШКИ ДЛЯ ОСТАЛЬНЫХ РЕЗОЛВЕРОВ ===
# [предположение] Эти резолверы пока оставляем как есть, но их тоже нужно будет упростить


@query.field("adminGetUserCommunityRoles")
@admin_auth_required
async def admin_get_user_community_roles(
    _: None, _info: GraphQLResolveInfo, author_id: int, community_id: int
) -> dict[str, Any]:
    """Получает роли пользователя в сообществе"""
    # [непроверенное] Временная заглушка - нужно вынести в сервис

    try:
        with local_session() as session:
            community_author = (
                session.query(CommunityAuthor)
                .where(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community_id)
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

    try:
        with local_session() as session:
            members_query = (
                session.query(Author, CommunityAuthor)
                .join(CommunityAuthor, Author.id == CommunityAuthor.author_id)
                .where(CommunityAuthor.community_id == community_id)
                .offset(offset)
                .limit(limit)
            )

            members: list[dict[str, Any]] = []
            for author, community_author in members_query:
                roles: list[str] = []
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
                .where(CommunityAuthor.community_id == community_id)
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

    try:
        with local_session() as session:
            community = session.query(Community).where(Community.id == community_id).first()
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


# === РЕАКЦИИ ===


@query.field("adminGetReactions")
@admin_auth_required
async def admin_get_reactions(
    _: None,
    _info: GraphQLResolveInfo,
    limit: int = 20,
    offset: int = 0,
    search: str = "",
    kind: str | None = None,
    shout_id: int | None = None,
    status: str = "all",
) -> dict[str, Any]:
    """Получает список реакций для админ-панели"""
    try:
        with local_session() as session:
            # Базовый запрос с джойнами
            query = (
                session.query(Reaction, Author, Shout)
                .join(Author, Reaction.created_by == Author.id)
                .join(Shout, Reaction.shout == Shout.id)
            )

            # Фильтрация
            filters: list[Any] = []

            # Фильтр по статусу (как в публикациях)
            if status == "active":
                filters.append(Reaction.deleted_at.is_(None))
            elif status == "deleted":
                filters.append(Reaction.deleted_at.isnot(None))
            # Если status == "all", не добавляем фильтр - показываем все

            if search:
                filters.append(
                    or_(
                        Reaction.body.ilike(f"%{search}%"),
                        Author.name.ilike(f"%{search}%"),
                        Author.email.ilike(f"%{search}%"),
                        Shout.title.ilike(f"%{search}%"),
                    )
                )
            if kind:
                filters.append(Reaction.kind == kind)
            if shout_id:
                filters.append(Reaction.shout == shout_id)

            if filters:
                query = query.where(and_(*filters))

            # Общее количество
            total = query.count()

            # Получаем реакции с пагинацией
            reactions_data = query.order_by(Reaction.created_at.desc()).offset(offset).limit(limit).all()

            # Формируем результат
            reactions: list[dict[str, Any]] = []
            for reaction, author, shout in reactions_data:
                # Получаем статистику для каждой реакции
                aliased_reaction = aliased(Reaction)
                stats = (
                    session.query(
                        func.count(aliased_reaction.id.distinct()).label("comments_count"),
                        func.sum(
                            case(
                                (aliased_reaction.kind == "LIKE", 1), (aliased_reaction.kind == "DISLIKE", -1), else_=0
                            )
                        ).label("rating"),
                    )
                    .where(
                        aliased_reaction.reply_to == reaction.id,
                        # Убираем фильтр deleted_at чтобы включить все реакции в статистику
                    )
                    .first()
                )

                reactions.append(
                    {
                        "id": reaction.id,
                        "kind": reaction.kind,
                        "body": reaction.body or "",
                        "created_at": reaction.created_at,
                        "updated_at": reaction.updated_at,
                        "deleted_at": reaction.deleted_at,
                        "reply_to": reaction.reply_to,
                        "created_by": {
                            "id": author.id,
                            "name": author.name,
                            "email": author.email,
                            "slug": author.slug,
                        },
                        "shout": {
                            "id": shout.id,
                            "title": shout.title,
                            "slug": shout.slug,
                            "layout": shout.layout,
                            "created_at": shout.created_at,
                            "published_at": shout.published_at,
                            "deleted_at": shout.deleted_at,
                        },
                        "stat": {
                            "comments_count": stats.comments_count if stats else 0,
                            "rating": stats.rating if stats else 0,
                        },
                    }
                )

            # Расчет пагинации
            per_page = limit
            total_pages = (total + per_page - 1) // per_page
            page = (offset // per_page) + 1

            logger.info(f"Загружено реакций для админ-панели: {len(reactions)}")
            return {
                "reactions": reactions,
                "total": total,
                "page": page,
                "perPage": per_page,
                "totalPages": total_pages,
            }

    except Exception as e:
        raise handle_error("получении списка реакций", e) from e


@mutation.field("adminUpdateReaction")
@admin_auth_required
async def admin_update_reaction(_: None, _info: GraphQLResolveInfo, reaction: dict[str, Any]) -> dict[str, Any]:
    """Обновляет реакцию"""
    try:
        reaction_id = reaction.get("id")
        if not reaction_id:
            return {"success": False, "error": "ID реакции не указан"}

        with local_session() as session:
            # Находим реакцию
            db_reaction = session.query(Reaction).where(Reaction.id == reaction_id).first()
            if not db_reaction:
                return {"success": False, "error": "Реакция не найдена"}

            # Обновляем поля
            if "body" in reaction:
                db_reaction.body = reaction["body"]
            if "deleted_at" in reaction:
                db_reaction.deleted_at = int(time.time())  # type: ignore[assignment]

            # Обновляем время изменения
            db_reaction.updated_at = int(time.time())  # type: ignore[assignment]

            session.commit()

            logger.info(f"Реакция {reaction_id} обновлена через админ-панель")
            return {"success": True}

    except Exception as e:
        logger.error(f"Ошибка обновления реакции: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminDeleteReaction")
@admin_auth_required
async def admin_delete_reaction(_: None, _info: GraphQLResolveInfo, reaction_id: int) -> dict[str, Any]:
    """Удаляет реакцию (мягкое удаление)"""
    try:
        with local_session() as session:
            # Находим реакцию
            db_reaction = session.query(Reaction).where(Reaction.id == reaction_id).first()
            if not db_reaction:
                return {"success": False, "error": "Реакция не найдена"}

            # Устанавливаем время удаления
            db_reaction.deleted_at = int(time.time())  # type: ignore[assignment]

            session.commit()

            logger.info(f"Реакция {reaction_id} удалена через админ-панель")
            return {"success": True}

    except Exception as e:
        logger.error(f"Ошибка удаления реакции: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminRestoreReaction")
@admin_auth_required
async def admin_restore_reaction(_: None, _info: GraphQLResolveInfo, reaction_id: int) -> dict[str, Any]:
    """Восстанавливает удаленную реакцию"""
    try:
        with local_session() as session:
            # Находим реакцию
            db_reaction = session.query(Reaction).where(Reaction.id == reaction_id).first()
            if not db_reaction:
                return {"success": False, "error": "Реакция не найдена"}

            # Убираем время удаления
            db_reaction.deleted_at = None

            session.commit()

            logger.info(f"Реакция {reaction_id} восстановлена через админ-панель")
            return {"success": True}

    except Exception as e:
        logger.error(f"Ошибка восстановления реакции: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminCreateCustomRole")
@admin_auth_required
async def admin_create_custom_role(_: None, _info: GraphQLResolveInfo, role: dict[str, Any]) -> dict[str, Any]:
    """Создает новую роль для сообщества"""
    try:
        role_id = role.get("id")
        name = role.get("name")
        description = role.get("description")
        icon = role.get("icon")
        community_id = role.get("community_id")

        if not role_id or not name or not community_id:
            return {"success": False, "error": "Необходимо указать id, name и community_id роли"}

        with local_session() as session:
            # Проверяем, существует ли сообщество
            community = session.query(Community).where(Community.id == community_id).first()
            if not community:
                return {"success": False, "error": "Сообщество не найдено"}

            # Проверяем, не существует ли уже роль с таким id
            existing_role = await redis.execute("HGET", f"community:custom_roles:{community_id}", role_id)
            if existing_role:
                return {"success": False, "error": "Роль с таким id уже существует"}

            # Создаем новую роль
            role_data = {
                "id": role_id,
                "name": name,
                "description": description or "",
                "icon": icon or "",
                "permissions": [],  # Пустой список разрешений для новой роли
            }

            # Сохраняем роль в Redis
            import json

            await redis.execute("HSET", f"community:custom_roles:{community_id}", role_id, json.dumps(role_data))

            logger.info(f"Создана новая роль {role_id} для сообщества {community_id}")
            return {"success": True, "role": {"id": role_id, "name": name, "description": description}}

    except Exception as e:
        logger.error(f"Ошибка создания роли: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminDeleteCustomRole")
@admin_auth_required
async def admin_delete_custom_role(
    _: None, _info: GraphQLResolveInfo, role_id: str, community_id: int
) -> dict[str, Any]:
    """Удаляет роль из сообщества"""
    try:
        with local_session() as session:
            # Проверяем, существует ли сообщество
            community = session.query(Community).where(Community.id == community_id).first()
            if not community:
                return {"success": False, "error": "Сообщество не найдено"}

            # Проверяем, существует ли роль
            existing_role = await redis.execute("HGET", f"community:custom_roles:{community_id}", role_id)
            if not existing_role:
                return {"success": False, "error": "Роль не найдена"}

            # Удаляем роль из Redis
            await redis.execute("HDEL", f"community:custom_roles:{community_id}", role_id)

            logger.info(f"Удалена роль {role_id} из сообщества {community_id}")
            return {"success": True}

    except Exception as e:
        logger.error(f"Ошибка удаления роли: {e}")
        return {"success": False, "error": str(e)}


@mutation.field("adminUpdatePermissions")
@admin_auth_required
async def admin_update_permissions(_: None, _info: GraphQLResolveInfo) -> dict[str, Any]:
    """Обновляет права для всех сообществ с новыми дефолтными настройками"""
    try:
        from services.rbac import update_all_communities_permissions

        await update_all_communities_permissions()

        logger.info("Права для всех сообществ обновлены")
        return {"success": True, "message": "Права обновлены для всех сообществ"}

    except Exception as e:
        logger.error(f"Ошибка обновления прав: {e}")
        return {"success": False, "error": str(e)}
