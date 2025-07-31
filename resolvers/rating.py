from typing import Any

from graphql import GraphQLResolveInfo
from sqlalchemy import and_, case, func, select, true
from sqlalchemy.orm import Session, aliased

from auth.orm import Author, AuthorRating
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor
from services.auth import login_required
from services.db import local_session
from services.schema import mutation, query
from utils.logger import root_logger as logger


@query.field("get_my_rates_comments")
@login_required
async def get_my_rates_comments(_: None, info: GraphQLResolveInfo, comments: list[int]) -> list[dict]:
    """
    Получение реакций пользователя на комментарии

    Args:
        info: Контекст запроса
        comments: Список ID комментариев

    Returns:
        list[dict]: Список словарей с реакциями пользователя на комментарии
        Каждый словарь содержит:
            - comment_id: ID комментария
            - my_rate: Тип реакции (LIKE/DISLIKE)
    """
    author_dict = info.context.get("author") if info.context else None
    author_id = author_dict.get("id") if author_dict else None
    if not author_id:
        return []  # Возвращаем пустой список вместо словаря с ошибкой

    # Подзапрос для реакций текущего пользователя
    rated_query = (
        select(Reaction.id.label("comment_id"), Reaction.kind.label("my_rate"))
        .where(
            and_(
                Reaction.reply_to.in_(comments),
                Reaction.created_by == author_id,
                Reaction.deleted_at.is_(None),
                Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]),
            )
        )
        .order_by(Reaction.shout, Reaction.created_at.desc())
        .distinct(Reaction.shout)
    )
    with local_session() as session:
        comments_result = session.execute(rated_query).all()
        # For each row, we need to extract the Reaction object and its attributes
        return [{"comment_id": reaction.id, "my_rate": reaction.kind} for (reaction,) in comments_result]


@query.field("get_my_rates_shouts")
@login_required
async def get_my_rates_shouts(_: None, info: GraphQLResolveInfo, shouts: list[int]) -> list[dict]:
    """
    Получение реакций пользователя на публикации
    """
    author_dict = info.context.get("author") if info.context else None
    author_id = author_dict.get("id") if author_dict else None

    if not author_id:
        return []

    with local_session() as session:
        try:
            stmt = (
                select(Reaction)
                .where(
                    and_(
                        Reaction.shout.in_(shouts),
                        Reaction.reply_to.is_(None),
                        Reaction.created_by == author_id,
                        Reaction.deleted_at.is_(None),
                        Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]),
                    )
                )
                .order_by(Reaction.shout, Reaction.created_at.desc())
                .distinct(Reaction.shout)
            )

            result = session.execute(stmt).all()

            return [
                {
                    "shout_id": reaction.shout,  # Получаем shout_id из объекта Reaction
                    "my_rate": reaction.kind,  # Получаем kind (my_rate) из объекта Reaction
                }
                for (reaction,) in result
            ]
        except Exception as e:
            logger.error(f"Error in get_my_rates_shouts: {e}")
            return []


@mutation.field("rate_author")
@login_required
async def rate_author(_: None, info: GraphQLResolveInfo, rated_slug: str, value: int) -> dict:
    rater_id = info.context.get("author", {}).get("id")
    with local_session() as session:
        rater_id = int(rater_id)
        rated_author = session.query(Author).where(Author.slug == rated_slug).first()
        if rater_id and rated_author:
            rating = (
                session.query(AuthorRating)
                .where(
                    and_(
                        AuthorRating.rater == rater_id,
                        AuthorRating.author == rated_author.id,
                    )
                )
                .first()
            )
            if rating:
                rating.plus = value > 0  # type: ignore[assignment]
                session.add(rating)
                session.commit()
                return {}
            try:
                rating = AuthorRating(rater=rater_id, author=rated_author.id, plus=value > 0)
                session.add(rating)
                session.commit()
            except Exception as err:
                return {"error": err}
    return {}


def count_author_comments_rating(session: Session, author_id: int) -> int:
    replied_alias = aliased(Reaction)
    replies_likes = (
        session.query(replied_alias)
        .join(Reaction, replied_alias.id == Reaction.reply_to)
        .where(
            and_(
                replied_alias.created_by == author_id,
                replied_alias.kind == ReactionKind.COMMENT.value,
            )
        )
        .where(replied_alias.kind == ReactionKind.LIKE.value)
        .count()
    ) or 0
    replies_dislikes = (
        session.query(replied_alias)
        .join(Reaction, replied_alias.id == Reaction.reply_to)
        .where(
            and_(
                replied_alias.created_by == author_id,
                replied_alias.kind == ReactionKind.COMMENT.value,
            )
        )
        .where(replied_alias.kind == ReactionKind.DISLIKE.value)
        .count()
    ) or 0

    return replies_likes - replies_dislikes


def count_author_replies_rating(session: Session, author_id: int) -> int:
    replied_alias = aliased(Reaction)
    replies_likes = (
        session.query(replied_alias)
        .join(Reaction, replied_alias.id == Reaction.reply_to)
        .where(
            and_(
                replied_alias.created_by == author_id,
                replied_alias.kind == ReactionKind.COMMENT.value,
            )
        )
        .where(replied_alias.kind == ReactionKind.LIKE.value)
        .count()
    ) or 0
    replies_dislikes = (
        session.query(replied_alias)
        .join(Reaction, replied_alias.id == Reaction.reply_to)
        .where(
            and_(
                replied_alias.created_by == author_id,
                replied_alias.kind == ReactionKind.COMMENT.value,
            )
        )
        .where(replied_alias.kind == ReactionKind.DISLIKE.value)
        .count()
    ) or 0

    return replies_likes - replies_dislikes


def count_author_shouts_rating(session: Session, author_id: int) -> int:
    shouts_likes = (
        session.query(Reaction, Shout)
        .join(Shout, Shout.id == Reaction.shout)
        .where(
            and_(
                Shout.authors.any(id=author_id),
                Reaction.kind == ReactionKind.LIKE.value,
            )
        )
        .count()
        or 0
    )
    shouts_dislikes = (
        session.query(Reaction, Shout)
        .join(Shout, Shout.id == Reaction.shout)
        .where(
            and_(
                Shout.authors.any(id=author_id),
                Reaction.kind == ReactionKind.DISLIKE.value,
            )
        )
        .count()
        or 0
    )
    return shouts_likes - shouts_dislikes


def get_author_rating_old(session: Session, author: Author) -> dict[str, int]:
    likes_count = (
        session.query(AuthorRating).where(and_(AuthorRating.author == author.id, AuthorRating.plus.is_(True))).count()
    )
    dislikes_count = (
        session.query(AuthorRating).where(and_(AuthorRating.author == author.id, AuthorRating.plus.is_(False))).count()
    )
    rating = likes_count - dislikes_count
    return {"rating": rating, "likes": likes_count, "dislikes": dislikes_count}


def get_author_rating_shouts(session: Session, author: Author) -> int:
    q = (
        select(
            Reaction.shout,
            case(
                (Reaction.kind == ReactionKind.LIKE.value, 1),
                (Reaction.kind == ReactionKind.DISLIKE.value, -1),
                else_=0,
            ).label("rating_value"),
        )
        .select_from(Reaction)
        .join(ShoutAuthor, Reaction.shout == ShoutAuthor.shout)
        .where(
            and_(
                ShoutAuthor.author == author.id,
                Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]),
                Reaction.deleted_at.is_(None),
            )
        )
    )

    results = session.execute(q)
    rating = 0
    for row in results:
        rating += row[1]

    return rating


def get_author_rating_comments(session: Session, author: Author) -> int:
    replied_comment = aliased(Reaction)
    q = (
        select(
            Reaction.id,
            case(
                (Reaction.kind == ReactionKind.LIKE.value, 1),
                (Reaction.kind == ReactionKind.DISLIKE.value, -1),
                else_=0,
            ).label("rating_value"),
        )
        .select_from(Reaction)
        .outerjoin(replied_comment, Reaction.reply_to == replied_comment.id)
        .join(Shout, Reaction.shout == Shout.id)
        .join(ShoutAuthor, Shout.id == ShoutAuthor.shout)
        .where(
            and_(
                ShoutAuthor.author == author.id,
                Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]),
                Reaction.created_by != author.id,
                Reaction.deleted_at.is_(None),
            )
        )
    )

    results = session.execute(q)
    rating = 0
    for row in results:
        rating += row[1]

    return rating


def add_author_rating_columns(q: Any, group_list: list[Any]) -> Any:
    # NOTE: method is not used

    # old karma
    q = q.outerjoin(AuthorRating, AuthorRating.author == Author.id)
    q = q.add_columns(func.sum(case((AuthorRating.plus == true(), 1), else_=-1)).label("rating"))

    # by shouts rating
    shout_reaction = aliased(Reaction)
    shouts_rating_subq = (
        select(
            Author.id,
            func.coalesce(
                func.sum(
                    case(
                        (shout_reaction.kind == ReactionKind.LIKE.value, 1),
                        (shout_reaction.kind == ReactionKind.DISLIKE.value, -1),
                        else_=0,
                    )
                ),
                0,
            ).label("shouts_rating"),
        )
        .select_from(shout_reaction)
        .outerjoin(Shout, Shout.authors.any(id=Author.id))
        .outerjoin(
            shout_reaction,
            and_(
                shout_reaction.reply_to.is_(None),
                shout_reaction.shout == Shout.id,
                shout_reaction.deleted_at.is_(None),
            ),
        )
        .group_by(Author.id)
        .subquery()
    )

    q = q.outerjoin(shouts_rating_subq, Author.id == shouts_rating_subq.c.id)
    q = q.add_columns(shouts_rating_subq.c.shouts_rating)
    group_list = [shouts_rating_subq.c.shouts_rating]

    # by comments
    replied_comment = aliased(Reaction)
    reaction_2 = aliased(Reaction)
    comments_subq = (
        select(
            Author.id,
            func.coalesce(
                func.sum(
                    case(
                        (reaction_2.kind == ReactionKind.LIKE.value, 1),
                        (reaction_2.kind == ReactionKind.DISLIKE.value, -1),
                        else_=0,
                    )
                ),
                0,
            ).label("comments_rating"),
        )
        .select_from(reaction_2)
        .outerjoin(
            replied_comment,
            and_(
                replied_comment.kind == ReactionKind.COMMENT.value,
                replied_comment.created_by == Author.id,
                reaction_2.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]),
                reaction_2.reply_to == replied_comment.id,
                reaction_2.deleted_at.is_(None),
            ),
        )
        .group_by(Author.id)
        .subquery()
    )

    q = q.outerjoin(comments_subq, Author.id == comments_subq.c.id)
    q = q.add_columns(comments_subq.c.comments_rating)
    group_list.extend([comments_subq.c.comments_rating])

    return q, group_list
