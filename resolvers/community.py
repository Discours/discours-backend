from typing import Any

from graphql import GraphQLResolveInfo
from sqlalchemy import distinct, func

from auth.orm import Author
from auth.permissions import ContextualPermissionCheck
from orm.community import Community, CommunityAuthor, CommunityFollower
from orm.shout import Shout, ShoutAuthor
from services.db import local_session
from services.rbac import require_any_permission, require_permission
from services.schema import mutation, query, type_community
from utils.logger import root_logger as logger


@query.field("get_communities_all")
async def get_communities_all(_: None, _info: GraphQLResolveInfo) -> list[Community]:
    with local_session() as session:
        return session.query(Community).all()


@query.field("get_community")
async def get_community(_: None, _info: GraphQLResolveInfo, slug: str) -> Community | None:
    q = local_session().query(Community).where(Community.slug == slug)
    return q.first()


@query.field("get_communities_by_author")
async def get_communities_by_author(
    _: None, _info: GraphQLResolveInfo, slug: str = "", user: str = "", author_id: int = 0
) -> list[Community]:
    with local_session() as session:
        q = session.query(Community).join(CommunityFollower)
        if slug:
            author = session.query(Author).where(Author.slug == slug).first()
            if author:
                author_id = author.id
                q = q.where(CommunityFollower.follower == author_id)
        if user:
            author = session.query(Author).where(Author.id == user).first()
            if author:
                author_id = author.id
                q = q.where(CommunityFollower.follower == author_id)
        if author_id:
            q = q.where(CommunityFollower.follower == author_id)
        return q.all()
    return []


@mutation.field("join_community")
@require_permission("community:read")
async def join_community(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    if not author_id:
        return {"ok": False, "error": "Unauthorized"}

    with local_session() as session:
        community = session.query(Community).where(Community.slug == slug).first()
        if not community:
            return {"ok": False, "error": "Community not found"}
        session.add(CommunityFollower(community=community.id, follower=int(author_id)))
        session.commit()
        return {"ok": True}


@mutation.field("leave_community")
async def leave_community(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    with local_session() as session:
        session.query(CommunityFollower).where(
            CommunityFollower.follower == author_id, CommunityFollower.community == slug
        ).delete()
        session.commit()
        return {"ok": True}


@mutation.field("create_community")
@require_permission("community:create")
async def create_community(_: None, info: GraphQLResolveInfo, community_input: dict[str, Any]) -> dict[str, Any]:
    # Получаем author_id из контекста через декоратор авторизации
    request = info.context.get("request")
    author_id = None

    if hasattr(request, "auth") and request.auth and hasattr(request.auth, "author_id"):
        author_id = request.auth.author_id
    elif hasattr(request, "scope") and "auth" in request.scope:
        auth_info = request.scope.get("auth", {})
        if isinstance(auth_info, dict):
            author_id = auth_info.get("author_id")
        elif hasattr(auth_info, "author_id"):
            author_id = auth_info.author_id

    if not author_id:
        return {"error": "Не удалось определить автора"}

    try:
        with local_session() as session:
            # Исключаем created_by из входных данных - он всегда из токена
            filtered_input = {k: v for k, v in community_input.items() if k != "created_by"}

            # Создаем новое сообщество с обязательным created_by из токена
            new_community = Community(created_by=author_id, **filtered_input)
            session.add(new_community)
            session.flush()  # Получаем ID сообщества

            # Инициализируем права ролей для нового сообщества
            await new_community.initialize_role_permissions()

            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка создания сообщества: {e!s}"}


@mutation.field("update_community")
@require_any_permission(["community:update_own", "community:update_any"])
async def update_community(_: None, info: GraphQLResolveInfo, community_input: dict[str, Any]) -> dict[str, Any]:
    # Получаем author_id из контекста через декоратор авторизации
    request = info.context.get("request")
    author_id = None

    if hasattr(request, "auth") and request.auth and hasattr(request.auth, "author_id"):
        author_id = request.auth.author_id
    elif hasattr(request, "scope") and "auth" in request.scope:
        auth_info = request.scope.get("auth", {})
        if isinstance(auth_info, dict):
            author_id = auth_info.get("author_id")
        elif hasattr(auth_info, "author_id"):
            author_id = auth_info.author_id

    if not author_id:
        return {"error": "Не удалось определить автора"}

    slug = community_input.get("slug")
    if not slug:
        return {"error": "Не указан slug сообщества"}

    try:
        with local_session() as session:
            # Находим сообщество для обновления
            community = session.query(Community).where(Community.slug == slug).first()
            if not community:
                return {"error": "Сообщество не найдено"}

            # Проверяем права на редактирование (создатель или админ/редактор)
            with local_session() as auth_session:
                # Получаем роли пользователя в сообществе
                community_author = (
                    auth_session.query(CommunityAuthor)
                    .where(CommunityAuthor.author_id == author_id, CommunityAuthor.community_id == community.id)
                    .first()
                )

                user_roles = community_author.role_list if community_author else []

                # Разрешаем редактирование если пользователь - создатель или имеет роль admin/editor
                if community.created_by != author_id and "admin" not in user_roles and "editor" not in user_roles:
                    return {"error": "Недостаточно прав для редактирования этого сообщества"}

            # Обновляем поля сообщества
            for key, value in community_input.items():
                # Исключаем изменение created_by - создатель не может быть изменен
                if hasattr(community, key) and key not in ["slug", "created_by"]:
                    setattr(community, key, value)

            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка обновления сообщества: {e!s}"}


@mutation.field("delete_community")
@require_any_permission(["community:delete_own", "community:delete_any"])
async def delete_community(root, info, slug: str) -> dict[str, Any]:
    try:
        # Используем local_session как контекстный менеджер
        with local_session() as session:
            # Находим сообщество по slug
            community = session.query(Community).where(Community.slug == slug).first()

            if not community:
                return {"error": "Сообщество не найдено", "success": False}

            # Проверяем права на удаление
            user_id = info.context.get("user_id", 0)
            permission_check = ContextualPermissionCheck()

            # Проверяем права на удаление сообщества
            if not await permission_check.can_delete_community(user_id, community, session):
                return {"error": "Недостаточно прав", "success": False}

            # Удаляем сообщество
            session.delete(community)
            session.commit()

            return {"success": True, "error": None}

    except Exception as e:
        # Логируем ошибку
        logger.error(f"Ошибка удаления сообщества: {e}")
        return {"error": str(e), "success": False}


@type_community.field("stat")
def resolve_community_stat(community: Community | dict[str, Any], *_: Any) -> dict[str, int]:
    """
    Резолвер поля stat для Community.
    Возвращает статистику сообщества: количество публикаций, подписчиков и авторов.
    """

    community_id = community.get("id") if isinstance(community, dict) else community.id

    try:
        with local_session() as session:
            # Количество опубликованных публикаций в сообществе
            shouts_count = (
                session.query(func.count(Shout.id))
                .where(Shout.community == community_id, Shout.published_at.is_not(None), Shout.deleted_at.is_(None))
                .scalar()
                or 0
            )

            # Количество подписчиков сообщества
            followers_count = (
                session.query(func.count(CommunityFollower.follower))
                .where(CommunityFollower.community == community_id)
                .scalar()
                or 0
            )

            # Количество уникальных авторов, опубликовавших в сообществе
            authors_count = (
                session.query(func.count(distinct(ShoutAuthor.author)))
                .join(Shout, ShoutAuthor.shout == Shout.id)
                .where(Shout.community == community_id, Shout.published_at.is_not(None), Shout.deleted_at.is_(None))
                .scalar()
                or 0
            )

            return {"shouts": int(shouts_count), "followers": int(followers_count), "authors": int(authors_count)}

    except Exception as e:
        logger.error(f"Ошибка при получении статистики сообщества {community_id}: {e}")
        # Возвращаем нулевую статистику при ошибке
        return {"shouts": 0, "followers": 0, "authors": 0}
