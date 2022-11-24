from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import desc, asc, select, case
from base.orm import local_session
from base.resolvers import query
from orm import ViewedEntry
from orm.shout import Shout, ShoutAuthor
from orm.reaction import Reaction, ReactionKind
from services.stat.reacted import ReactedStorage


def add_rating_column(q):
    return q.join(Reaction).add_columns(sa.func.sum(case(
        (Reaction.kind == ReactionKind.AGREE, 1),
        (Reaction.kind == ReactionKind.DISAGREE, -1),
        (Reaction.kind == ReactionKind.PROOF, 1),
        (Reaction.kind == ReactionKind.DISPROOF, -1),
        (Reaction.kind == ReactionKind.ACCEPT, 1),
        (Reaction.kind == ReactionKind.REJECT, -1),
        (Reaction.kind == ReactionKind.LIKE, 1),
        (Reaction.kind == ReactionKind.DISLIKE, -1),
        else_=0
    )).label('rating'))


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


@query.field("loadShout")
async def load_shout(_, info, slug):
    with local_session() as session:
        q = select(Shout).options(
            # TODO add cation
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        q = add_rating_column(q)
        q = q.filter(
            Shout.slug == slug
        ).filter(
            Shout.deletedAt.is_(None)
        ).group_by(Shout.id)

        [shout, rating] = session.execute(q).unique().one()

        shout.stat = await ReactedStorage.get_shout_stat(shout.slug, rating)

        return shout


def map_result_item(result_item):
    shout = result_item[0]
    shout.rating = result_item[1]
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
    q = add_rating_column(q)

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

    with_author_captions = False if options.get('with_author_captions') is None else options.get('with_author_captions')

    query_order_by = desc(order_by) if order_by_desc else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)
    q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

    with local_session() as session:
        shouts = list(map(map_result_item, session.execute(q).unique()))

        for shout in shouts:
            shout.stat = await ReactedStorage.get_shout_stat(shout.slug, shout.rating)
            del shout.rating

            author_captions = {}

            if with_author_captions:
                author_captions_result = session.query(ShoutAuthor).where(
                    ShoutAuthor.shout.in_(map(lambda s: s.slug, shouts))).all()

                for author_captions_result_item in author_captions_result:
                    if author_captions.get(author_captions_result_item.shout) is None:
                        author_captions[author_captions_result_item.shout] = {}

                    author_captions[
                        author_captions_result_item.shout
                    ][
                        author_captions_result_item.user
                    ] = author_captions_result_item.caption

                for author in shout.authors:
                    author.caption = author_captions[shout.slug][author.slug]

    return shouts
