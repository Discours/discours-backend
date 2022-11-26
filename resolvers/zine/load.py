from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import desc, asc, select, case
from base.orm import local_session
from base.resolvers import query
from orm import ViewedEntry
from orm.shout import Shout
from orm.reaction import Reaction, ReactionKind
from services.zine.shoutauthor import ShoutAuthorStorage
from services.stat.viewed import ViewedStorage


def calc_reactions(q):
    return q.join(Reaction).add_columns(
        sa.func.sum(case(
            (Reaction.kind == ReactionKind.AGREE, 1),
            (Reaction.kind == ReactionKind.DISAGREE, -1),
            (Reaction.kind == ReactionKind.PROOF, 1),
            (Reaction.kind == ReactionKind.DISPROOF, -1),
            (Reaction.kind == ReactionKind.ACCEPT, 1),
            (Reaction.kind == ReactionKind.REJECT, -1),
            (Reaction.kind == ReactionKind.LIKE, 1),
            (Reaction.kind == ReactionKind.DISLIKE, -1),
            else_=0)
        ).label('rating'),
        sa.func.sum(
            case(
                (Reaction.body.is_not(None), 1),
                else_=0
            )
        ).label('commented')
    )


def apply_filters(q, filters, user=None):
    filters = {} if filters is None else filters
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
        q = calc_reactions(q)
        q = q.filter(
            Shout.slug == slug
        ).filter(
            Shout.deletedAt.is_(None)
        ).group_by(Shout.id)

        [shout, rating, commented] = session.execute(q).unique().one()
        for a in shout.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(shout.slug, a.slug)
        viewed = await ViewedStorage.get_shout(shout.slug)
        shout.stat = {
            "rating": rating,
            "viewed": viewed,
            "commented": commented,
            # "reacted": reacted
        }

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
        order_by: 'createdAt'
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
    user = info.context["request"].user
    q = apply_filters(q, options.get("filters"), user)
    q = calc_reactions(q)

    o = options.get("order_by")
    if o:
        if o == 'comments':
            q = q.add_columns(sa.func.count(Reaction.id).label(o))
            q = q.join(Reaction, Shout.slug == Reaction.shout)
            q = q.filter(Reaction.body.is_not(None))
        elif o == 'reacted':
            q = q.join(
                Reaction
            ).add_columns(
                sa.func.max(Reaction.createdAt).label(o)
            )
        elif o == 'views':
            q = q.join(ViewedEntry)
            q = q.add_columns(sa.func.sum(ViewedEntry.amount).label(o))
        order_by = o
    else:
        order_by = Shout.createdAt

    order_by_desc = True if options.get('order_by_desc') is None else options.get('order_by_desc')

    query_order_by = desc(order_by) if order_by_desc else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)
    q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

    shouts = []
    with local_session() as session:
        for [shout, rating, commented] in session.execute(q).unique():
            shout.stat = {
                "rating": rating,
                "viewed": await ViewedStorage.get_shout(shout.slug),
                "commented": commented,
                # "reacted": reacted
            }
            # NOTE: no need authors captions in arrays
            # for author in shout.authors:
            #    author.caption = await ShoutAuthorStorage.get_author_caption(shout.slug, author.slug)
            shouts.append(shout)
    return shouts
