from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import desc, asc, select, case
from base.orm import local_session
from base.resolvers import query
from orm.shout import Shout
from orm.reaction import Reaction, ReactionKind
from services.zine.shoutauthor import ShoutAuthorStorage
from services.stat.reacted import ReactedStorage


def apply_filters(q, filters, user=None):
    filters = {} if filters is None else filters
    if filters.get("reacted") and user:
        q.join(Reaction, Reaction.createdBy == user.slug)
    if filters.get("visibility"):
        q = q.filter(Shout.visibility == filters.get("visibility"))
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
        before = datetime.now() - timedelta(days=int(filters.get("days")) or 30)
        q = q.filter(Shout.createdAt > before)
    return q


def extract_order(o, q):
    if o:
        q = q.add_columns(sa.func.count(Reaction.id).label(o))
        if o == 'comments':
            q = q.join(Reaction, Shout.slug == Reaction.shout)
            q = q.filter(Reaction.body.is_not(None))
        elif o == 'reacted':
            q = q.join(
                Reaction
            ).add_columns(
                sa.func.max(Reaction.createdAt).label(o)
            )
        elif o == "rating":
            q = q.join(Reaction).add_columns(sa.func.sum(case(
                (Reaction.kind == ReactionKind.AGREE, 1),
                (Reaction.kind == ReactionKind.DISAGREE, -1),
                (Reaction.kind == ReactionKind.PROOF, 1),
                (Reaction.kind == ReactionKind.DISPROOF, -1),
                (Reaction.kind == ReactionKind.ACCEPT, 1),
                (Reaction.kind == ReactionKind.REJECT, -1),
                (Reaction.kind == ReactionKind.LIKE, 1),
                (Reaction.kind == ReactionKind.DISLIKE, -1),
                else_=0
            )).label(o))
        return o
    else:
        return 'createdAt'


@query.field("loadShout")
async def load_shout(_, info, slug):
    with local_session() as session:
        shout = session.query(Shout).options(
            # TODO add cation
            selectinload(Shout.authors),
            selectinload(Shout.topics),
        ).filter(
            Shout.slug == slug
        ).filter(
            Shout.deletedAt.is_(None)
        ).one()

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
        # TODO add caption
        selectinload(Shout.authors),
        selectinload(Shout.topics),
    ).where(
        Shout.deletedAt.is_(None)
    )
    user = info.context["request"].user
    q = apply_filters(q, options.get("filters"), user)

    order_by = extract_order(options.get("order_by"), q)

    order_by_desc = True if options.get('order_by_desc') is None else options.get('order_by_desc')

    query_order_by = desc(order_by) if order_by_desc else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)
    q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

    with local_session() as session:
        shouts = list(map(lambda r: r.Shout, session.execute(q)))
        for s in shouts:
            s.stat = await ReactedStorage.get_shout_stat(s.slug)
            for a in s.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)

    return shouts
