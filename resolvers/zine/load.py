from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.sql.expression import desc, asc, select, func, case

from auth.credentials import AuthCredentials
from base.exceptions import ObjectNotExist
from base.orm import local_session
from base.resolvers import query
from orm import ViewedEntry
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor


def add_stat_columns(q):
    aliased_reaction = aliased(Reaction)

    q = q.outerjoin(aliased_reaction).add_columns(
        func.sum(
            aliased_reaction.id
        ).label('reacted_stat'),
        func.sum(
            case(
                (aliased_reaction.body.is_not(None), 1),
                else_=0
            )
        ).label('commented_stat'),
        func.sum(case(
            # do not count comments' reactions
            (aliased_reaction.replyTo.is_not(None), 0),
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


def apply_filters(q, filters, user_id=None):
    if filters.get("reacted") and user_id:
        q.join(Reaction, Reaction.createdBy == user_id)

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

        try:
            [shout, reacted_stat, commented_stat, rating_stat] = session.execute(q).first()

            viewed_stat_query = select().select_from(
                Shout
            ).where(
                Shout.id == shout.id
            ).join(
                ViewedEntry
            ).group_by(
                Shout.id
            ).add_columns(
                func.sum(ViewedEntry.amount).label('viewed_stat')
            )

            # Debug tip:
            # print(viewed_stat_query.compile(compile_kwargs={"literal_binds": True}))
            viewed_stat = session.execute(viewed_stat_query).scalar()

            shout.stat = {
                "viewed": viewed_stat,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat
            }

            for author_caption in session.query(ShoutAuthor).join(Shout).where(Shout.slug == slug):
                for author in shout.authors:
                    if author.id == author_caption.user:
                        author.caption = author_caption.caption
            return shout
        except Exception:
            raise ObjectNotExist("Slug was not found: %s" % slug)


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

    auth: AuthCredentials = info.context["request"].auth
    q = apply_filters(q, options.get("filters", {}), auth.user_id)

    order_by = options.get("order_by", Shout.createdAt)
    if order_by == 'reacted':
        aliased_reaction = aliased(Reaction)
        q.outerjoin(aliased_reaction).add_columns(func.max(aliased_reaction.createdAt).label('reacted'))

    query_order_by = desc(order_by) if options.get('order_by_desc', True) else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)

    q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

    with local_session() as session:
        shouts = []
        shouts_map = {}

        for [shout, reacted_stat, commented_stat, rating_stat] in session.execute(q).unique():
            shouts.append(shout)
            shout.stat = {
                "viewed": 0,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat
            }
            shouts_map[shout.id] = shout

        viewed_stat_query = select(
            Shout.id
        ).where(
            Shout.id.in_(shouts_map.keys())
        ).join(
            ViewedEntry
        ).group_by(
            Shout.id
        ).add_columns(
            func.sum(ViewedEntry.amount).label('viewed_stat')
        )

        for [shout_id, viewed_stat] in session.execute(viewed_stat_query).unique():
            shouts.append(shout)
            shouts_map[shout_id].stat['viewed'] = viewed_stat

    return shouts
