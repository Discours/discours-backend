from typing import Any

from graphql import GraphQLResolveInfo

from auth.decorators import editor_or_admin_required
from auth.orm import Author
from orm.community import Community, CommunityFollower
from services.db import local_session
from services.schema import mutation, query, type_community


@query.field("get_communities_all")
async def get_communities_all(_: None, _info: GraphQLResolveInfo) -> list[Community]:
    from sqlalchemy.orm import joinedload

    with local_session() as session:
        # Загружаем сообщества с проверкой существования авторов
        communities = (
            session.query(Community)
            .options(joinedload(Community.created_by_author))
            .join(
                Author,
                Community.created_by == Author.id,  # INNER JOIN - исключает сообщества без авторов
            )
            .filter(
                Community.created_by.isnot(None),  # Дополнительная проверка
                Author.id.isnot(None),  # Проверяем что автор существует
            )
            .all()
        )

        # Дополнительная проверка валидности данных
        valid_communities = []
        for community in communities:
            if (
                community.created_by
                and hasattr(community, "created_by_author")
                and community.created_by_author
                and community.created_by_author.id
            ):
                valid_communities.append(community)
            else:
                from utils.logger import root_logger as logger

                logger.warning(f"Исключено сообщество {community.id} ({community.slug}) - проблемы с автором")

        return valid_communities


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
            author_id = session.query(Author).where(Author.slug == slug).first().id
            q = q.where(CommunityFollower.author == author_id)
        if user:
            author_id = session.query(Author).where(Author.id == user).first().id
            q = q.where(CommunityFollower.author == author_id)
        if author_id:
            q = q.where(CommunityFollower.author == author_id)
        return q.all()
    return []


@mutation.field("join_community")
async def join_community(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    with local_session() as session:
        community = session.query(Community).where(Community.slug == slug).first()
        if not community:
            return {"ok": False, "error": "Community not found"}
        session.add(CommunityFollower(community=community.id, follower=author_id))
        session.commit()
        return {"ok": True}


@mutation.field("leave_community")
async def leave_community(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    with local_session() as session:
        session.query(CommunityFollower).where(
            CommunityFollower.author == author_id, CommunityFollower.community == slug
        ).delete()
        session.commit()
        return {"ok": True}


@mutation.field("create_community")
@editor_or_admin_required
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
            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка создания сообщества: {e!s}"}


@mutation.field("update_community")
@editor_or_admin_required
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
            community = session.query(Community).filter(Community.slug == slug).first()
            if not community:
                return {"error": "Сообщество не найдено"}

            # Проверяем права на редактирование (создатель или админ/редактор)
            with local_session() as auth_session:
                author = auth_session.query(Author).filter(Author.id == author_id).first()
                user_roles = [role.id for role in author.roles] if author and author.roles else []

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
@editor_or_admin_required
async def delete_community(_: None, info: GraphQLResolveInfo, slug: str) -> dict[str, Any]:
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
            # Находим сообщество для удаления
            community = session.query(Community).filter(Community.slug == slug).first()
            if not community:
                return {"error": "Сообщество не найдено"}

            # Проверяем права на удаление (создатель или админ/редактор)
            with local_session() as auth_session:
                author = auth_session.query(Author).filter(Author.id == author_id).first()
                user_roles = [role.id for role in author.roles] if author and author.roles else []

                # Разрешаем удаление если пользователь - создатель или имеет роль admin/editor
                if community.created_by != author_id and "admin" not in user_roles and "editor" not in user_roles:
                    return {"error": "Недостаточно прав для удаления этого сообщества"}

            # Удаляем сообщество
            session.delete(community)
            session.commit()
            return {"error": None}
    except Exception as e:
        return {"error": f"Ошибка удаления сообщества: {e!s}"}


@type_community.field("created_by")
def resolve_community_created_by(obj: Community, *_: Any) -> Author:
    """
    Резолвер поля created_by для Community.
    Возвращает автора, создавшего сообщество.
    """
    # Если связь уже загружена через joinedload и валидна
    if hasattr(obj, "created_by_author") and obj.created_by_author and obj.created_by_author.id:
        return obj.created_by_author

    # Критическая ошибка - это не должно происходить после фильтрации в get_communities_all
    from utils.logger import root_logger as logger

    logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Резолвер created_by вызван для сообщества {obj.id} без валидного автора")
    error_message = f"Сообщество {obj.id} не имеет валидного создателя"
    raise ValueError(error_message)


@type_community.field("stat")
def resolve_community_stat(obj: Community, *_: Any) -> dict[str, int]:
    """
    Резолвер поля stat для Community.
    Возвращает статистику сообщества: количество публикаций, подписчиков и авторов.
    """
    from sqlalchemy import distinct, func

    from orm.shout import Shout, ShoutAuthor

    try:
        with local_session() as session:
            # Количество опубликованных публикаций в сообществе
            shouts_count = (
                session.query(func.count(Shout.id))
                .filter(Shout.community == obj.id, Shout.published_at.is_not(None), Shout.deleted_at.is_(None))
                .scalar()
                or 0
            )

            # Количество подписчиков сообщества
            followers_count = (
                session.query(func.count(CommunityFollower.follower))
                .filter(CommunityFollower.community == obj.id)
                .scalar()
                or 0
            )

            # Количество уникальных авторов, опубликовавших в сообществе
            authors_count = (
                session.query(func.count(distinct(ShoutAuthor.author)))
                .join(Shout, ShoutAuthor.shout == Shout.id)
                .filter(Shout.community == obj.id, Shout.published_at.is_not(None), Shout.deleted_at.is_(None))
                .scalar()
                or 0
            )

            return {"shouts": int(shouts_count), "followers": int(followers_count), "authors": int(authors_count)}

    except Exception as e:
        from utils.logger import root_logger as logger

        logger.error(f"Ошибка при получении статистики сообщества {obj.id}: {e}")
        # Возвращаем нулевую статистику при ошибке
        return {"shouts": 0, "followers": 0, "authors": 0}
