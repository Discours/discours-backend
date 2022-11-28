from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.sql.expression import desc, asc, select, case
from base.orm import local_session
from base.resolvers import query
from orm import ViewedEntry
from orm.shout import Shout, ShoutAuthor
from orm.reaction import Reaction, ReactionKind


def add_stat_columns(q):
    q = q.outerjoin(ViewedEntry).add_columns(sa.func.sum(ViewedEntry.amount).label('viewed_stat'))

    aliased_reaction = aliased(Reaction)

    q = q.outerjoin(aliased_reaction).add_columns(
        sa.func.sum(
            aliased_reaction.id
        ).label('reacted_stat'),
        sa.func.sum(
            case(
                (aliased_reaction.body.is_not(None), 1),
                else_=0
            )
        ).label('commented_stat'),
        sa.func.sum(case(
            (aliased_reaction.kind == ReactionKind.AGREE, 1),
            (aliased_reaction.kind == ReactionKind.DISAGREE, -1),
            (aliased_reaction.kind == ReactionKind.PROOF, 1),
            (aliased_reaction.kind == ReactionKind.DISPROOF, -1),
            (aliased_reaction.kind == ReactionKind.ACCEPT, 1),
            (aliased_reaction.kind == ReactionKind.REJECT, -1),
            (aliased_reaction.kind == ReactionKind.LIKE, 1),
            (aliased_reaction.kind == ReactionKind.DISLIKE, -1),
            else_=0)
        ).label('rating_stat'))

    return q


def apply_filters(q, filters, user=None):

    if filters.get("reacted") and user:
        q.join(Reaction, Reaction.createdBy == user.slug)

    v = filters.get("visibility")
    if v == "public":
        q = q.filter(Shout.visibility == filters.get("visibility"))
    if v == "community":
        q = q.filter(Shout.visibility.in_(["public", "community"]))

    if filters.get("layout"):
        q = q.filter(Shout.layout == filters.get("layout"))
    if filters.get("author"):
        q = q.filter(Shout.authors.any(slug=filters.get("author")))
    if filters.get("topic"):
        q = q.filter(Shout.topics.any(slug=filters.get("topic")))
    if filters.get("title"):
        q = q.filter(Shout.title.ilike(f'%{filters.get("title")}%'))
    if filters.get("body"):
        q = q.filter(Shout.body.ilike(f'%{filters.get("body")}%s'))
    if filters.get("days"):
        before = datetime.now(tz=timezone.utc) - timedelta(days=int(filters.get("days")) or 30)
        q = q.filter(Shout.createdAt > before)

    return q


@query.field("loadShout")
async def load_shout(_, info, slug):
    with local_session() as session:
        q = select(Shout).options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        q = add_stat_columns(q)
        q = q.filter(
            Shout.slug == slug
        ).filter(
            Shout.deletedAt.is_(None)
        ).group_by(Shout.id)

        [shout, viewed_stat, reacted_stat, commented_stat, rating_stat] = session.execute(q).unique().one()

        shout.stat = {
            "viewed": viewed_stat,
            "reacted": reacted_stat,
            "commented": commented_stat,
            "rating": rating_stat
        }

        for author_caption in session.query(ShoutAuthor).where(ShoutAuthor.shout == slug):
            for author in shout.authors:
                if author.slug == author_caption.user:
                    author.caption = author_caption.caption

        return shout


@query.field("loadShouts")
async def load_shouts_by(_, info, options):
    """
    :param options: {
        filters: {
            layout: 'audio',
            visibility: "public",
            author: 'discours',
            topic: 'culture',
            title: 'something',
            body: 'something else',
            days: 30
        }
        offset: 0
        limit: 50
        order_by: 'createdAt' | 'commented' | 'reacted' | 'rating'
        order_by_desc: true

    }
    :return: Shout[]
    """

    q = select(Shout).options(
        joinedload(Shout.authors),
        joinedload(Shout.topics),
    ).where(
        Shout.deletedAt.is_(None)
    )

    q = add_stat_columns(q)

    user = info.context["request"].user
    q = apply_filters(q, options.get("filters", {}), user)

    order_by = options.get("order_by", Shout.createdAt)
    if order_by == 'reacted':
        aliased_reaction = aliased(Reaction)
        q.outerjoin(aliased_reaction).add_columns(sa.func.max(aliased_reaction.createdAt).label('reacted'))

    order_by_desc = options.get('order_by_desc', True)

    query_order_by = desc(order_by) if order_by_desc else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)

    q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

    with local_session() as session:
        shouts = []

        for [shout, viewed_stat, reacted_stat, commented_stat, rating_stat] in session.execute(q).unique():
            shouts.append(shout)

            shout.stat = {
                "viewed": viewed_stat,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat
            }

    return shouts
