import time
import traceback
from typing import Any

from graphql import GraphQLResolveInfo
from sqlalchemy import Select, and_, asc, case, desc, func, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql import ColumnElement

from auth.orm import Author
from orm.rating import (
    NEGATIVE_REACTIONS,
    POSITIVE_REACTIONS,
    PROPOSAL_REACTIONS,
    RATING_REACTIONS,
    is_positive,
)
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor
from resolvers.follower import follow
from resolvers.proposals import handle_proposing
from resolvers.stat import update_author_stat
from services.auth import add_user_role, login_required
from services.db import local_session
from services.notify import notify_reaction
from services.schema import mutation, query
from utils.logger import root_logger as logger


def query_reactions() -> Select:
    """
    Base query for fetching reactions with associated authors and shouts.

    :return: Base query.
    """
    return (
        select(
            Reaction,
            Author,
            Shout,
        )
        .select_from(Reaction)
        .join(Author, Reaction.created_by == Author.id)
        .join(Shout, Reaction.shout == Shout.id)
    )


def add_reaction_stat_columns(q: Select) -> Select:
    """
    Add statistical columns to a reaction query.

    :param q: SQL query for reactions.
    :return: Query with added statistics columns.
    """
    aliased_reaction = aliased(Reaction)
    # Join reactions and add statistical columns
    return q.outerjoin(
        aliased_reaction,
        and_(
            aliased_reaction.reply_to == Reaction.id,
            aliased_reaction.deleted_at.is_(None),
        ),
    ).add_columns(
        # Count unique comments
        func.coalesce(
            func.count(aliased_reaction.id).where(aliased_reaction.kind == ReactionKind.COMMENT.value), 0
        ).label("comments_stat"),
        # Calculate rating as the difference between likes and dislikes
        func.sum(
            case(
                (aliased_reaction.kind == ReactionKind.LIKE.value, 1),
                (aliased_reaction.kind == ReactionKind.DISLIKE.value, -1),
                else_=0,
            )
        ).label("rating_stat"),
    )


def get_reactions_with_stat(q: Select, limit: int = 10, offset: int = 0) -> list[dict]:
    """
    Execute the reaction query and retrieve reactions with statistics.

    :param q: Query with reactions and statistics.
    :param limit: Number of reactions to load.
    :param offset: Pagination offset.
    :return: List of reactions as dictionaries.

    >>> get_reactions_with_stat(q, 10, 0)  # doctest: +SKIP
    [{'id': 1, 'body': 'Текст комментария', 'stat': {'rating': 5, 'comments_count': 3}, ...}]
    """
    # Убираем distinct() поскольку GROUP BY уже обеспечивает уникальность,
    # а distinct() вызывает ошибку PostgreSQL с JSON полями
    q = q.limit(limit).offset(offset)
    reactions: list[dict] = []

    with local_session() as session:
        result_rows = session.execute(q).unique()
        for reaction, author, shout, comments_count, rating_stat in result_rows:
            # Пропускаем реакции с отсутствующими shout или author
            if not shout or not author:
                logger.error(f"Пропущена реакция из-за отсутствия shout или author: {reaction.dict()}")
                continue

            # Преобразуем Reaction в словарь для доступа по ключу
            reaction_dict = reaction.dict()

            # Обработка поля created_by
            if author:
                reaction_dict["created_by"] = author.dict()
            else:
                # Если автор не найден, создаем заглушку
                logger.warning(f"Автор не найден для реакции {reaction.id}")
                reaction_dict["created_by"] = {
                    "id": reaction.created_by or 0,
                    "name": f"Unknown User {reaction.created_by or 0}",
                    "slug": f"user-{reaction.created_by or 0}",
                    "email": "unknown@example.com",
                    "created_at": 0,
                }

            reaction_dict["shout"] = shout.dict()
            reaction_dict["stat"] = {"rating": rating_stat, "comments_count": comments_count}
            reactions.append(reaction_dict)

    return reactions


def is_featured_author(session: Session, author_id: int) -> bool:
    """
    Check if an author has at least one non-deleted featured article.

    :param session: Database session.
    :param author_id: Author ID.
    :return: True if the author has a featured article, else False.
    """
    return session.query(
        session.query(Shout)
        .where(Shout.authors.any(id=author_id))
        .where(Shout.featured_at.is_not(None), Shout.deleted_at.is_(None))
        .exists()
    ).scalar()


def check_to_feature(session: Session, approver_id: int, reaction: dict) -> bool:
    """
    Make a shout featured if it receives more than 4 votes from authors.

    :param session: Database session.
    :param approver_id: Approver author ID.
    :param reaction: Reaction object.
    :return: True if shout should be featured, else False.
    """
    is_positive_kind = reaction.get("kind") == ReactionKind.LIKE.value
    if not reaction.get("reply_to") and is_positive_kind:
        # Проверяем, не содержит ли пост более 20% дизлайков
        # Если да, то не должен быть featured независимо от количества лайков
        if check_to_unfeature(session, reaction):
            return False

        # Собираем всех авторов, поставивших лайк
        author_approvers = set()
        reacted_readers = (
            session.query(Reaction.created_by)
            .where(
                Reaction.shout == reaction.get("shout"),
                Reaction.kind.in_(POSITIVE_REACTIONS),
                # Рейтинги (LIKE, DISLIKE) физически удаляются, поэтому фильтр deleted_at не нужен
            )
            .distinct()
            .all()
        )

        # Добавляем текущего одобряющего
        approver = session.query(Author).where(Author.id == approver_id).first()
        if approver and is_featured_author(session, approver_id):
            author_approvers.add(approver_id)

        # Проверяем, есть ли у реагировавших авторов featured публикации
        for (reader_id,) in reacted_readers:
            if is_featured_author(session, reader_id):
                author_approvers.add(reader_id)

        # Публикация становится featured при наличии более 4 лайков от авторов
        logger.debug(f"Публикация {reaction.get('shout')} имеет {len(author_approvers)} лайков от авторов")
        return len(author_approvers) > 4
    return False


def check_to_unfeature(session: Session, reaction: dict) -> bool:
    """
    Unfeature a shout if:
    1. Less than 5 positive votes, OR
    2. 20% or more of reactions are negative.

    :param session: Database session.
    :param reaction: Reaction object.
    :return: True if shout should be unfeatured, else False.
    """
    if not reaction.get("reply_to"):
        shout_id = reaction.get("shout")

        # Проверяем соотношение дизлайков, даже если текущая реакция не дизлайк
        total_reactions = (
            session.query(Reaction)
            .where(
                Reaction.shout == shout_id,
                Reaction.reply_to.is_(None),
                Reaction.kind.in_(RATING_REACTIONS),
                # Рейтинги физически удаляются при удалении, поэтому фильтр deleted_at не нужен
            )
            .count()
        )

        positive_reactions = (
            session.query(Reaction)
            .where(
                Reaction.shout == shout_id,
                Reaction.kind.in_(POSITIVE_REACTIONS),
                Reaction.reply_to.is_(None),
                # Рейтинги физически удаляются при удалении, поэтому фильтр deleted_at не нужен
            )
            .count()
        )

        negative_reactions = (
            session.query(Reaction)
            .where(
                Reaction.shout == shout_id,
                Reaction.kind.in_(NEGATIVE_REACTIONS),
                Reaction.reply_to.is_(None),
                # Рейтинги физически удаляются при удалении, поэтому фильтр deleted_at не нужен
            )
            .count()
        )

        # Условие 1: Меньше 5 голосов "за"
        if positive_reactions < 5:
            logger.debug(f"Публикация {shout_id}: {positive_reactions} лайков (меньше 5) - должна быть unfeatured")
            return True

        # Условие 2: Проверяем, составляют ли отрицательные реакции 20% или более от всех реакций
        negative_ratio = negative_reactions / total_reactions if total_reactions > 0 else 0
        logger.debug(
            f"Публикация {shout_id}: {negative_reactions}/{total_reactions} отрицательных реакций ({negative_ratio:.2%})"
        )
        if total_reactions > 0 and negative_ratio >= 0.2:
            return True

    return False


async def set_featured(session: Session, shout_id: int) -> None:
    """
    Feature a shout and update the author's role.

    :param session: Database session.
    :param shout_id: Shout ID.
    """
    s = session.query(Shout).where(Shout.id == shout_id).first()
    if s:
        current_time = int(time.time())
        # Use setattr to avoid MyPy complaints about Column assignment
        s.featured_at = current_time  # type: ignore[assignment]
        session.commit()
        author = session.query(Author).where(Author.id == s.created_by).first()
        if author:
            await add_user_role(str(author.id))
        session.add(s)
        session.commit()


def set_unfeatured(session: Session, shout_id: int) -> None:
    """
    Unfeature a shout.

    :param session: Database session.
    :param shout_id: Shout ID.
    """
    session.query(Shout).where(Shout.id == shout_id).update({"featured_at": None})
    session.commit()


async def _create_reaction(session: Session, shout_id: int, is_author: bool, author_id: int, reaction: dict) -> dict:
    """
    Create a new reaction and perform related actions such as updating counters and notification.

    :param session: Database session.
    :param shout_id: Shout ID.
    :param is_author: Flag indicating if the user is the author of the shout.
    :param author_id: Author ID.
    :param reaction: Dictionary with reaction data.
    :return: Dictionary with created reaction data.
    """
    r = Reaction(**reaction)
    session.add(r)
    session.commit()
    rdict = r.dict()

    # Update author stat for comments
    if r.kind == ReactionKind.COMMENT.value:
        update_author_stat(author_id)

    # Handle proposal
    if r.reply_to and r.kind in PROPOSAL_REACTIONS and is_author:
        reply_to = int(r.reply_to)
        if reply_to:
            handle_proposing(ReactionKind(r.kind), reply_to, shout_id)

    # Handle rating
    if r.kind in RATING_REACTIONS:
        # Проверяем, является ли публикация featured
        shout = session.query(Shout).where(Shout.id == shout_id).first()
        is_currently_featured = shout and shout.featured_at is not None

        # Проверяем сначала условие для unfeature (для уже featured публикаций)
        if is_currently_featured and check_to_unfeature(session, rdict):
            set_unfeatured(session, shout_id)
            logger.info(f"Публикация {shout_id} потеряла статус featured из-за условий unfeaturing")
        # Только если не было unfeature, проверяем условие для feature
        elif not is_currently_featured and check_to_feature(session, author_id, rdict):
            await set_featured(session, shout_id)
            logger.info(f"Публикация {shout_id} получила статус featured благодаря лайкам от авторов")

    # Notify creation
    await notify_reaction(r, "create")

    return rdict


def prepare_new_rating(reaction: dict, shout_id: int, session: Session, author_id: int) -> dict[str, Any] | None:
    """
    Check for the possibility of rating a shout.

    :param reaction: Dictionary with reaction data.
    :param shout_id: Shout ID.
    :param session: Database session.
    :param author_id: Author ID.
    :return: Dictionary with error or None.
    """
    kind = reaction.get("kind")
    if kind in RATING_REACTIONS:
        opposite_kind = ReactionKind.DISLIKE.value if is_positive(kind) else ReactionKind.LIKE.value

        existing_ratings = (
            session.query(Reaction)
            .where(
                Reaction.shout == shout_id,
                Reaction.created_by == author_id,
                Reaction.kind.in_(RATING_REACTIONS),
                Reaction.deleted_at.is_(None),
            )
            .all()
        )

        for r in existing_ratings:
            if r.kind == kind:
                return {"error": "You can't rate the same thing twice"}
            if r.kind == opposite_kind:
                return {"error": "Remove opposite vote first"}
        if shout_id in [r.shout for r in existing_ratings]:
            return {"error": "You can't rate your own thing"}

    return None


@mutation.field("create_reaction")
@login_required
async def create_reaction(_: None, info: GraphQLResolveInfo, reaction: dict) -> dict:
    """
    Create a new reaction through a GraphQL request.

    :param info: GraphQL context info.
    :param reaction: Dictionary with reaction data.
    :return: Dictionary with created reaction data or error.
    """
    reaction_input = reaction
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    shout_id = int(reaction_input.get("shout", "0"))

    logger.debug(f"Creating reaction with data: {reaction_input}")
    logger.debug(f"Author ID: {author_id}, Shout ID: {shout_id}")

    if not author_id:
        return {"error": "Author ID is required to create a reaction."}
    if not shout_id:
        return {"error": "Shout ID is required to create a reaction."}

    try:
        with local_session() as session:
            authors = session.query(ShoutAuthor.author).where(ShoutAuthor.shout == shout_id).scalar()
            is_author = (
                bool(list(filter(lambda x: x == int(author_id), authors))) if isinstance(authors, list) else False
            )
            reaction_input["created_by"] = author_id
            kind = reaction_input.get("kind")

            # handle ratings
            if kind in RATING_REACTIONS:
                logger.debug(f"creating rating reaction: {kind}")
                error_result = prepare_new_rating(reaction_input, shout_id, session, author_id)
                if error_result:
                    logger.error(f"Rating preparation error: {error_result}")
                    return error_result

            # handle all reactions
            rdict = await _create_reaction(session, shout_id, is_author, author_id, reaction_input)
            logger.debug(f"Created reaction result: {rdict}")

            # follow if liked
            if kind == ReactionKind.LIKE.value:
                follow(None, info, "shout", shout_id=shout_id)
            shout = session.query(Shout).where(Shout.id == shout_id).first()
            if not shout:
                return {"error": "Shout not found"}
            rdict["shout"] = shout.dict()
            rdict["created_by"] = author_dict
            return {"reaction": rdict}
    except Exception as e:
        traceback.print_exc()
        logger.error(f"{type(e).__name__}: {e}")
        return {"error": "Cannot create reaction."}


@mutation.field("update_reaction")
@login_required
async def update_reaction(_: None, info: GraphQLResolveInfo, reaction: dict) -> dict:
    """
    Update an existing reaction through a GraphQL request.

    :param info: GraphQL context info.
    :param reaction: Dictionary with reaction data.
    :return: Dictionary with updated reaction data or error.
    """
    author_id = info.context.get("author", {}).get("id")
    roles = info.context.get("roles")
    rid = reaction.get("id")

    if not rid or not author_id or not roles:
        return {"error": "Invalid input data"}

    del reaction["id"]

    with local_session() as session:
        try:
            reaction_query = query_reactions().where(Reaction.id == rid)
            reaction_query = add_reaction_stat_columns(reaction_query)
            reaction_query = reaction_query.group_by(Reaction.id, Author.id, Shout.id)

            result = session.execute(reaction_query).unique().first()
            if result:
                r, author, _shout, comments_count, rating_stat = result
                if not r or not author:
                    return {"error": "Invalid reaction ID or unauthorized"}

                if r.created_by != author.id and "editor" not in roles:
                    return {"error": "Access denied"}

                # Update reaction
                r.body = reaction.get("body", r.body)
                r.updated_at = int(time.time())
                Reaction.update(r, reaction)
                session.add(r)
                session.commit()

                r.stat = {
                    "comments_count": comments_count,
                    "rating": rating_stat,
                }

                await notify_reaction(r, "update")

                return {"reaction": r.dict()}
            return {"error": "Reaction not found"}
        except Exception as e:
            logger.error(f"{type(e).__name__}: {e}")
            return {"error": "Cannot update reaction"}


@mutation.field("delete_reaction")
@login_required
async def delete_reaction(_: None, info: GraphQLResolveInfo, reaction_id: int) -> dict:
    """
    Delete an existing reaction through a GraphQL request.

    :param info: GraphQL context info.
    :param reaction_id: Reaction ID to delete.
    :return: Dictionary with deleted reaction data or error.
    """
    author_id = info.context.get("author", {}).get("id")
    roles = info.context.get("roles", [])

    if not author_id:
        return {"error": "UnauthorizedError"}

    with local_session() as session:
        try:
            author = session.query(Author).where(Author.id == author_id).one()
            r = session.query(Reaction).where(Reaction.id == reaction_id).one()

            if r.created_by != author_id and "editor" not in roles:
                return {"error": "Access denied"}

            if r.kind == ReactionKind.COMMENT.value:
                r.deleted_at = int(time.time())
                update_author_stat(author.id)
                session.add(r)
                session.commit()
            elif r.kind == ReactionKind.PROPOSE.value:
                r.deleted_at = int(time.time())
                session.add(r)
                session.commit()
                # TODO: add more reaction types here
            else:
                logger.debug(f"{author_id} user removing his #{reaction_id} reaction")
                reaction_dict = r.dict()
                # Проверяем, является ли публикация featured до удаления реакции
                shout = session.query(Shout).where(Shout.id == r.shout).first()
                is_currently_featured = shout and shout.featured_at is not None

                session.delete(r)
                session.commit()

                # Проверяем условие unfeatured только для уже featured публикаций
                if is_currently_featured and check_to_unfeature(session, reaction_dict):
                    set_unfeatured(session, r.shout)

            await notify_reaction(r, "delete")

            return {"error": None, "reaction": r.dict()}
        except Exception as e:
            logger.error(f"{type(e).__name__}: {e}")
            return {"error": "Cannot delete reaction"}


def apply_reaction_filters(by: dict, q: Select) -> Select:
    """
    Apply filters to a reaction query.

    :param by: Dictionary with filter parameters.
    :param q: SQL query.
    :return: Query with applied filters.
    """
    shout_slug = by.get("shout")
    if shout_slug:
        q = q.where(Shout.slug == shout_slug)

    shout_id = by.get("shout_id")
    if shout_id:
        q = q.where(Shout.id == shout_id)

    shouts = by.get("shouts")
    if shouts:
        q = q.where(Shout.slug.in_(shouts))

    created_by = by.get("created_by", by.get("author_id"))
    if created_by:
        q = q.where(Author.id == created_by)

    author_slug = by.get("author")
    if author_slug:
        q = q.where(Author.slug == author_slug)

    topic = by.get("topic")
    if isinstance(topic, int):
        q = q.where(Shout.topics.any(id=topic))

    kinds = by.get("kinds")
    if isinstance(kinds, list):
        q = q.where(Reaction.kind.in_(kinds))

    if by.get("reply_to"):
        q = q.where(Reaction.reply_to == by.get("reply_to"))

    by_search = by.get("search", "")
    if len(by_search) > 2:
        q = q.where(Reaction.body.ilike(f"%{by_search}%"))

    after = by.get("after")
    if isinstance(after, int):
        q = q.where(Reaction.created_at > after)

    return q


@query.field("load_reactions_by")
async def load_reactions_by(
    _: None, _info: GraphQLResolveInfo, by: dict, limit: int = 50, offset: int = 0
) -> list[dict]:
    """
    Load reactions based on specified parameters.

    :param info: GraphQL context info.
    :param by: Filter parameters.
    :param limit: Number of reactions to load.
    :param offset: Pagination offset.
    :return: List of reactions.
    """
    q = query_reactions()

    # Add statistics and apply filters
    q = add_reaction_stat_columns(q)
    q = apply_reaction_filters(by, q)

    # Include reactions with deleted_at for building comment trees
    # q = q.where(Reaction.deleted_at.is_(None))

    # Group and sort
    q = q.group_by(Reaction.id, Author.id, Shout.id)
    order_stat = by.get("sort", "").lower()
    order_by_stmt: ColumnElement = desc(Reaction.created_at)
    if order_stat == "oldest":
        order_by_stmt = asc(Reaction.created_at)
    elif order_stat.endswith("like"):
        order_by_stmt = desc("rating_stat")
    q = q.order_by(order_by_stmt)

    # Retrieve and return reactions
    return get_reactions_with_stat(q, limit, offset)


@query.field("load_shout_ratings")
async def load_shout_ratings(
    _: None, info: GraphQLResolveInfo, shout: int, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    """
    Load ratings for a specified shout with pagination.

    :param info: GraphQL context info.
    :param shout: Shout ID.
    :param limit: Number of reactions to load.
    :param offset: Pagination offset.
    :return: List of reactions.
    """
    q = query_reactions()

    # Filter, group, sort, limit, offset
    q = q.where(
        and_(
            Reaction.deleted_at.is_(None),
            Reaction.shout == shout,
            Reaction.kind.in_(RATING_REACTIONS),
        )
    )
    q = q.group_by(Reaction.id, Author.id, Shout.id)
    q = q.order_by(desc(Reaction.created_at))

    # Retrieve and return reactions
    return get_reactions_with_stat(q, limit, offset)


@query.field("load_shout_comments")
async def load_shout_comments(
    _: None, info: GraphQLResolveInfo, shout: int, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """
    Load comments for a specified shout with pagination and statistics.

    :param info: GraphQL context info.
    :param shout: Shout ID.
    :param limit: Number of comments to load.
    :param offset: Pagination offset.
    :return: List of reactions.
    """
    q = query_reactions()

    q = add_reaction_stat_columns(q)

    # Filter, group, sort, limit, offset
    q = q.where(
        and_(
            Reaction.deleted_at.is_(None),
            Reaction.shout == shout,
            Reaction.body.is_not(None),
        )
    )
    q = q.group_by(Reaction.id, Author.id, Shout.id)
    q = q.order_by(desc(Reaction.created_at))

    # Retrieve and return reactions
    return get_reactions_with_stat(q, limit, offset)


@query.field("load_comment_ratings")
async def load_comment_ratings(
    _: None, info: GraphQLResolveInfo, comment: int, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """
    Load ratings for a specified comment with pagination.

    :param info: GraphQL context info.
    :param comment: Comment ID.
    :param limit: Number of ratings to load.
    :param offset: Pagination offset.
    :return: List of ratings.
    """
    q = query_reactions()

    # Filter, group, sort, limit, offset
    q = q.where(
        and_(
            Reaction.deleted_at.is_(None),
            Reaction.reply_to == comment,
            Reaction.kind.in_(RATING_REACTIONS),
        )
    )
    q = q.group_by(Reaction.id, Author.id, Shout.id)
    q = q.order_by(desc(Reaction.created_at))

    # Retrieve and return reactions
    return get_reactions_with_stat(q, limit, offset)


@query.field("load_comments_branch")
async def load_comments_branch(
    _: None,
    _info: GraphQLResolveInfo,
    shout: int,
    parent_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "newest",
    children_limit: int = 3,
    children_offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Загружает иерархические комментарии с возможностью пагинации корневых и дочерних.

    :param info: GraphQL context info.
    :param shout: ID статьи.
    :param parent_id: ID родительского комментария (None для корневых).
    :param limit: Количество комментариев для загрузки.
    :param offset: Смещение для пагинации.
    :param sort: Порядок сортировки ('newest', 'oldest', 'like').
    :param children_limit: Максимальное количество дочерних комментариев.
    :param children_offset: Смещение для дочерних комментариев.
    :return: Список комментариев с дочерними.
    """
    # Создаем базовый запрос
    q = query_reactions()
    q = add_reaction_stat_columns(q)

    # Фильтруем по статье и типу (комментарии)
    q = q.where(
        and_(
            Reaction.deleted_at.is_(None),
            Reaction.shout == shout,
            Reaction.kind == ReactionKind.COMMENT.value,
        )
    )

    # Фильтруем по родительскому ID
    q = q.where(Reaction.reply_to.is_(None)) if parent_id is None else q.where(Reaction.reply_to == parent_id)

    # Сортировка и группировка
    q = q.group_by(Reaction.id, Author.id, Shout.id)

    # Определяем сортировку
    order_by_stmt = None
    if sort.lower() == "oldest":
        order_by_stmt = asc(Reaction.created_at)
    elif sort.lower() == "like":
        order_by_stmt = desc("rating_stat")
    else:  # "newest" по умолчанию
        order_by_stmt = desc(Reaction.created_at)

    q = q.order_by(order_by_stmt)

    # Выполняем запрос для получения комментариев
    comments = get_reactions_with_stat(q, limit, offset)

    # Если комментарии найдены, загружаем дочерние и количество ответов
    if comments:
        # Загружаем количество ответов для каждого комментария
        await load_replies_count(comments)

        # Загружаем дочерние комментарии
        await load_first_replies(comments, children_limit, children_offset, sort)

    return comments


async def load_replies_count(comments: list[Any]) -> None:
    """
    Загружает количество ответов для списка комментариев и обновляет поле stat.comments_count.

    :param comments: Список комментариев, для которых нужно загрузить количество ответов.
    """
    if not comments:
        return

    comment_ids = [comment["id"] for comment in comments]

    # Запрос для подсчета количества ответов
    q = (
        select(Reaction.reply_to.label("parent_id"), func.count().label("count"))
        .where(
            and_(
                Reaction.reply_to.in_(comment_ids),
                Reaction.deleted_at.is_(None),
                Reaction.kind == ReactionKind.COMMENT.value,
            )
        )
        .group_by(Reaction.reply_to)
    )

    # Выполняем запрос
    with local_session() as session:
        result = session.execute(q).fetchall()

    # Создаем словарь {parent_id: count}
    replies_count = {row[0]: row[1] for row in result}

    # Добавляем значения в комментарии
    for comment in comments:
        if "stat" not in comment:
            comment["stat"] = {}

        # Обновляем счетчик комментариев в stat
        comment["stat"]["comments_count"] = replies_count.get(comment["id"], 0)


async def load_first_replies(comments: list[Any], limit: int, offset: int, sort: str = "newest") -> None:
    """
    Загружает первые N ответов для каждого комментария.

    :param comments: Список комментариев, для которых нужно загрузить ответы.
    :param limit: Максимальное количество ответов для каждого комментария.
    :param offset: Смещение для пагинации дочерних комментариев.
    :param sort: Порядок сортировки ответов.
    """
    if not comments or limit <= 0:
        return

    # Собираем ID комментариев
    comment_ids = [comment["id"] for comment in comments]

    # Базовый запрос для загрузки ответов
    q = query_reactions()
    q = add_reaction_stat_columns(q)

    # Фильтрация: только ответы на указанные комментарии
    q = q.where(
        and_(
            Reaction.reply_to.in_(comment_ids),
            Reaction.deleted_at.is_(None),
            Reaction.kind == ReactionKind.COMMENT.value,
        )
    )

    # Группировка
    q = q.group_by(Reaction.id, Author.id, Shout.id)

    # Определяем сортировку
    order_by_stmt = None
    if sort.lower() == "oldest":
        order_by_stmt = asc(Reaction.created_at)
    elif sort.lower() == "like":
        order_by_stmt = desc("rating_stat")
    else:  # "newest" по умолчанию
        order_by_stmt = desc(Reaction.created_at)

    q = q.order_by(order_by_stmt, Reaction.reply_to)

    # Выполняем запрос - указываем limit для неограниченного количества ответов
    # но не более 100 на родительский комментарий
    replies = get_reactions_with_stat(q, limit=100, offset=0)

    # Группируем ответы по родительским ID
    replies_by_parent: dict[int, list[dict[str, Any]]] = {}
    for reply in replies:
        parent_id = reply.get("reply_to")
        if parent_id is not None and parent_id not in replies_by_parent:
            replies_by_parent[parent_id] = []
        if parent_id is not None:
            replies_by_parent[parent_id].append(reply)

    # Добавляем ответы к соответствующим комментариям с учетом смещения и лимита
    for comment in comments:
        comment_id = comment["id"]
        if comment_id in replies_by_parent:
            parent_replies = replies_by_parent[comment_id]
            # Применяем смещение и лимит
            comment["first_replies"] = parent_replies[offset : offset + limit]
        else:
            comment["first_replies"] = []

    # Загружаем количество ответов для дочерних комментариев
    all_replies = [reply for replies in replies_by_parent.values() for reply in replies]
    if all_replies:
        await load_replies_count(all_replies)
