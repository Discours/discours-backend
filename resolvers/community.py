import traceback
from typing import Any

from graphql import GraphQLResolveInfo
from sqlalchemy import distinct, func

from auth.orm import Author
from orm.community import Community, CommunityAuthor, CommunityFollower
from orm.shout import Shout, ShoutAuthor
from services.db import local_session
from services.rbac import (
    RBACError,
    get_user_roles_from_context,
    require_any_permission,
    require_permission,
    roles_have_permission,
)
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
        return {"error": "Не удалось определить автора", "success": False}

    try:
        with local_session() as session:
            # Исключаем created_by из входных данных - он всегда из токена
            filtered_input = {k: v for k, v in community_input.items() if k != "created_by"}

            # Создаем новое сообщество
            new_community = Community(**filtered_input, created_by=author_id)
            session.add(new_community)
            session.commit()

            return {"error": None, "success": True}
    except Exception as e:
        return {"error": f"Ошибка создания сообщества: {e!s}", "success": False}


@mutation.field("update_community")
@require_any_permission(["community:update", "community:update_any"])
async def update_community(_: None, info: GraphQLResolveInfo, community_input: dict[str, Any]) -> dict[str, Any]:
    if not community_input.get("slug"):
        return {"error": "Не указан slug сообщества", "success": False}

    try:
        with local_session() as session:
            # Находим сообщество по slug
            community = session.query(Community).where(Community.slug == community_input["slug"]).first()

            if not community:
                return {"error": "Сообщество не найдено", "success": False}

            # Обновляем поля сообщества
            for key, value in community_input.items():
                # Исключаем изменение created_by - создатель не может быть изменен
                if hasattr(community, key) and key not in ["slug", "created_by"]:
                    setattr(community, key, value)

            session.commit()
            return {"error": None, "success": True}
    except Exception as e:
        return {"error": f"Ошибка обновления сообщества: {e!s}", "success": False}


@mutation.field("delete_community")
async def delete_community(root, info, slug: str) -> dict[str, Any]:
    try:
        logger.info(f"[delete_community] Начинаем удаление сообщества с slug: {slug}")

        # Находим community_id и устанавливаем в контекст для RBAC ПЕРЕД проверкой прав
        with local_session() as session:
            community = session.query(Community).where(Community.slug == slug).first()
            if community:
                logger.debug(f"[delete_community] Тип info.context: {type(info.context)}, содержимое: {info.context!r}")
                if isinstance(info.context, dict):
                    info.context["community_id"] = community.id
                else:
                    logger.error(
                        f"[delete_community] Неожиданный тип контекста: {type(info.context)}. Попытка присвоить community_id через setattr."
                    )
                    info.context.community_id = community.id
                logger.debug(f"[delete_community] Установлен community_id в контекст: {community.id}")
            else:
                logger.warning(f"[delete_community] Сообщество с slug '{slug}' не найдено")
                return {"error": "Сообщество не найдено", "success": False}

        # Теперь проверяем права с правильным community_id
        user_roles, community_id = get_user_roles_from_context(info)
        logger.debug(f"[delete_community] user_roles: {user_roles}, community_id: {community_id}")

        has_permission = False
        for permission in ["community:delete", "community:delete_any"]:
            if await roles_have_permission(user_roles, permission, community_id):
                has_permission = True
                break

        if not has_permission:
            raise RBACError("Недостаточно прав. Требуется любое из: ", ["community:delete", "community:delete_any"])

        # Используем local_session как контекстный менеджер
        with local_session() as session:
            # Находим сообщество по slug
            community = session.query(Community).where(Community.slug == slug).first()

            if not community:
                logger.warning(f"[delete_community] Сообщество с slug '{slug}' не найдено")
                return {"error": "Сообщество не найдено", "success": False}

            logger.info(f"[delete_community] Найдено сообщество: id={community.id}, name={community.name}")

            # Проверяем связанные записи
            followers_count = (
                session.query(CommunityFollower).where(CommunityFollower.community == community.id).count()
            )
            authors_count = session.query(CommunityAuthor).where(CommunityAuthor.community_id == community.id).count()
            shouts_count = session.query(Shout).where(Shout.community == community.id).count()

            logger.info(
                f"[delete_community] Связанные записи: followers={followers_count}, authors={authors_count}, shouts={shouts_count}"
            )

            # Удаляем связанные записи
            if followers_count > 0:
                logger.info(f"[delete_community] Удаляем {followers_count} подписчиков")
                session.query(CommunityFollower).where(CommunityFollower.community == community.id).delete()

            if authors_count > 0:
                logger.info(f"[delete_community] Удаляем {authors_count} авторов")
                session.query(CommunityAuthor).where(CommunityAuthor.community_id == community.id).delete()

            # Удаляем сообщество
            logger.info(f"[delete_community] Удаляем сообщество {community.id}")
            session.delete(community)
            session.commit()

            logger.info(f"[delete_community] Сообщество {community.id} успешно удалено")
            return {"success": True, "error": None}

    except Exception as e:
        # Логируем ошибку
        logger.error(f"[delete_community] Ошибка удаления сообщества: {e}")
        logger.error(f"[delete_community] Traceback: {traceback.format_exc()}")
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


@type_community.field("created_by")
def resolve_community_created_by(community: Community, *_: Any) -> Author | None:
    """
    Резолвер для поля created_by сообщества.
    Возвращает автора-создателя сообщества или None, если создатель не найден.
    """
    with local_session() as session:
        # Если у сообщества нет created_by, возвращаем None
        if not community.created_by:
            return None

        # Ищем автора в базе данных
        author = session.query(Author).where(Author.id == community.created_by).first()
        if not author:
            logger.warning(f"Автор с ID {community.created_by} не найден для сообщества {community.id}")
            return None

        return author
