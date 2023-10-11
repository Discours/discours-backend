from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy.sql.expression import (
    desc,
    asc,
    select,
    func,
    case,
    and_,
    # text,
    nulls_last,
)

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from services.db import local_session
from services.schema import query
from orm import TopicFollower
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.user import AuthorFollower


def add_stat_columns(q):
    aliased_reaction = aliased(Reaction)

    q = q.outerjoin(aliased_reaction).add_columns(
        func.sum(aliased_reaction.id).label("reacted_stat"),
        func.sum(
            case((aliased_reaction.kind == ReactionKind.COMMENT, 1), else_=0)
        ).label("commented_stat"),
        func.sum(
            case(
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
                else_=0,
            )
        ).label("rating_stat"),
        func.max(
            case(
                (aliased_reaction.kind != ReactionKind.COMMENT, None),
                else_=aliased_reaction.createdAt,
            )
        ).label("last_comment"),
    )

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
    if filters.get("excludeLayout"):
        q = q.filter(Shout.layout != filters.get("excludeLayout"))
    if filters.get("author"):
        q = q.filter(Shout.authors.any(slug=filters.get("author")))
    if filters.get("topic"):
        q = q.filter(Shout.topics.any(slug=filters.get("topic")))
    if filters.get("title"):
        q = q.filter(Shout.title.ilike(f'%{filters.get("title")}%'))
    if filters.get("body"):
        q = q.filter(Shout.body.ilike(f'%{filters.get("body")}%s'))
    if filters.get("days"):
        before = datetime.now(tz=timezone.utc) - timedelta(
            days=int(filters.get("days")) or 30
        )
        q = q.filter(Shout.createdAt > before)

    return q


@query.field("loadShout")
async def load_shout(_, info, slug=None, shout_id=None):
    with local_session() as session:
        q = select(Shout).options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        q = add_stat_columns(q)

        if slug is not None:
            q = q.filter(Shout.slug == slug)

        if shout_id is not None:
            q = q.filter(Shout.id == shout_id)

        q = q.filter(Shout.deletedAt.is_(None)).group_by(Shout.id)

        resp = session.execute(q).first()
        if resp:
            [
                shout,
                reacted_stat,
                commented_stat,
                rating_stat,
                last_comment,
            ] = resp

            shout.stat = {
                "viewed": shout.views,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat,
            }

            for author_caption in (
                session.query(ShoutAuthor).join(Shout).where(Shout.slug == slug)
            ):
                for author in shout.authors:
                    if author.id == author_caption.user:
                        author.caption = author_caption.caption
            return shout
        else:
            print("Slug was not found: %s" % slug)
            return


@query.field("loadShouts")
async def load_shouts_by(_, info, options):
    """
    :param options: {
        filters: {
            layout: 'music',
            excludeLayout: 'article',
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

    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .where(and_(Shout.deletedAt.is_(None), Shout.layout.is_not(None)))
    )

    q = add_stat_columns(q)

    auth: AuthCredentials = info.context["request"].auth
    q = apply_filters(q, options.get("filters", {}), auth.user_id)

    order_by = options.get("order_by", Shout.publishedAt)

    query_order_by = (
        desc(order_by) if options.get("order_by_desc", True) else asc(order_by)
    )
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)

    q = (
        q.group_by(Shout.id)
        .order_by(nulls_last(query_order_by))
        .limit(limit)
        .offset(offset)
    )

    shouts = []
    with local_session() as session:
        shouts_map = {}

        for [
            shout,
            reacted_stat,
            commented_stat,
            rating_stat,
            last_comment,
        ] in session.execute(q).unique():
            shouts.append(shout)
            shout.stat = {
                "viewed": shout.views,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat,
            }
            shouts_map[shout.id] = shout

    return shouts


@query.field("loadDrafts")
@login_required
async def get_drafts(_, info):
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id

    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .where(and_(Shout.deletedAt.is_(None), Shout.createdBy == user_id))
    )

    q = q.group_by(Shout.id)

    shouts = []
    with local_session() as session:
        for [shout] in session.execute(q).unique():
            shouts.append(shout)

    return shouts


@query.field("myFeed")
@login_required
async def get_my_feed(_, info, options):
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id

    subquery = (
        select(Shout.id)
        .join(ShoutAuthor)
        .join(AuthorFollower, AuthorFollower.follower == user_id)
        .join(ShoutTopic)
        .join(TopicFollower, TopicFollower.follower == user_id)
    )

    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .where(
            and_(
                Shout.publishedAt.is_not(None),
                Shout.deletedAt.is_(None),
                Shout.id.in_(subquery),
            )
        )
    )

    q = add_stat_columns(q)
    q = apply_filters(q, options.get("filters", {}), user_id)

    order_by = options.get("order_by", Shout.publishedAt)

    query_order_by = (
        desc(order_by) if options.get("order_by_desc", True) else asc(order_by)
    )
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)

    q = (
        q.group_by(Shout.id)
        .order_by(nulls_last(query_order_by))
        .limit(limit)
        .offset(offset)
    )

    shouts = []
    with local_session() as session:
        shouts_map = {}
        for [
            shout,
            reacted_stat,
            commented_stat,
            rating_stat,
            last_comment,
        ] in session.execute(q).unique():
            shouts.append(shout)
            shout.stat = {
                "viewed": shout.views,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat,
            }
            shouts_map[shout.id] = shout

    return shouts
