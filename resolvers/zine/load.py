import json
from datetime import datetime, timedelta

from sqlalchemy.orm import aliased, joinedload
from sqlalchemy.sql.expression import and_, asc, case, desc, func, nulls_last, select

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.exceptions import ObjectNotExist
from base.orm import local_session
from base.resolvers import query
from orm import TopicFollower
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.user import AuthorFollower


def get_shouts_from_query(q):
    shouts = []
    with local_session() as session:
        for [shout, reacted_stat, commented_stat, rating_stat, last_comment] in session.execute(
            q
        ).unique():
            shouts.append(shout)
            shout.stat = {
                "viewed": shout.views,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat,
            }

    return shouts


def get_rating_func(aliased_reaction):
    return func.sum(
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
    )


def add_stat_columns(q):
    aliased_reaction = aliased(Reaction)

    q = q.outerjoin(aliased_reaction).add_columns(
        func.sum(aliased_reaction.id).label("reacted_stat"),
        func.sum(case((aliased_reaction.kind == ReactionKind.COMMENT, 1), else_=0)).label(
            "commented_stat"
        ),
        get_rating_func(aliased_reaction).label("rating_stat"),
        func.max(
            case(
                (aliased_reaction.kind != ReactionKind.COMMENT, None),
                else_=aliased_reaction.createdAt,
            )
        ).label("last_comment"),
    )

    return q


def apply_filters(q, filters, user_id=None):  # noqa: C901
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
    if filters.get("fromDate"):
        # fromDate: '2022-12-31
        date_from = datetime.strptime(filters.get("fromDate"), "%Y-%m-%d")
        q = q.filter(Shout.createdAt >= date_from)
    if filters.get("toDate"):
        # toDate: '2023-12-31'
        date_to = datetime.strptime(filters.get("toDate"), "%Y-%m-%d")
        q = q.filter(Shout.createdAt < (date_to + timedelta(days=1)))

    return q


@query.field("loadShout")
async def load_shout(_, info, slug=None, shout_id=None):
    # for testing, soon will be removed
    if slug == "testtesttest":
        with open("test/test.json") as json_file:
            test_shout = json.load(json_file)["data"]["loadShout"]
            test_shout["createdAt"] = datetime.fromisoformat(test_shout["createdAt"])
            test_shout["publishedAt"] = datetime.fromisoformat(test_shout["publishedAt"])
            return test_shout

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

        try:
            [shout, reacted_stat, commented_stat, rating_stat, last_comment] = session.execute(
                q
            ).first()

            shout.stat = {
                "viewed": shout.views,
                "reacted": reacted_stat,
                "commented": commented_stat,
                "rating": rating_stat,
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
            layout: 'music',
            excludeLayout: 'article',
            visibility: "public",
            author: 'discours',
            topic: 'culture',
            title: 'something',
            body: 'something else',
            fromDate: '2022-12-31',
            toDate: '2023-12-31'
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

    query_order_by = desc(order_by) if options.get("order_by_desc", True) else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)

    q = q.group_by(Shout.id).order_by(nulls_last(query_order_by)).limit(limit).offset(offset)

    return get_shouts_from_query(q)


@query.field("loadRandomTopShouts")
async def load_random_top_shouts(_, info, params):
    """
    :param params: {
        filters: {
            layout: 'music',
            excludeLayout: 'article',
            fromDate: '2022-12-31'
            toDate: '2023-12-31'
        }
        fromRandomCount: 100,
        limit: 50
    }
    :return: Shout[]
    """

    aliased_reaction = aliased(Reaction)

    subquery = (
        select(Shout.id)
        .outerjoin(aliased_reaction)
        .where(and_(Shout.deletedAt.is_(None), Shout.layout.is_not(None)))
    )

    subquery = apply_filters(subquery, params.get("filters", {}))
    subquery = subquery.group_by(Shout.id).order_by(desc(get_rating_func(aliased_reaction)))

    from_random_count = params.get("fromRandomCount")
    if from_random_count:
        subquery = subquery.limit(from_random_count)

    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .where(Shout.id.in_(subquery))
    )

    q = add_stat_columns(q)

    limit = params.get("limit", 10)
    q = q.group_by(Shout.id).order_by(func.random()).limit(limit)

    # print(q.compile(compile_kwargs={"literal_binds": True}))

    return get_shouts_from_query(q)


@query.field("loadUnratedShouts")
async def load_unrated_shouts(_, info, limit):
    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .outerjoin(
            Reaction,
            and_(
                Reaction.shout == Shout.id,
                Reaction.replyTo.is_(None),
                Reaction.kind.in_([ReactionKind.LIKE, ReactionKind.DISLIKE]),
            ),
        )
        .where(and_(Shout.deletedAt.is_(None), Shout.layout.is_not(None), Reaction.id.is_(None)))
    )

    q = add_stat_columns(q)

    q = q.group_by(Shout.id).order_by(desc(Shout.createdAt)).limit(limit)

    # print(q.compile(compile_kwargs={"literal_binds": True}))

    return get_shouts_from_query(q)


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

    user_followed_authors = select(AuthorFollower.author).where(AuthorFollower.follower == user_id)
    user_followed_topics = select(TopicFollower.topic).where(TopicFollower.follower == user_id)

    subquery = (
        select(Shout.id)
        .where(Shout.id == ShoutAuthor.shout)
        .where(Shout.id == ShoutTopic.shout)
        .where(
            (ShoutAuthor.user.in_(user_followed_authors))
            | (ShoutTopic.topic.in_(user_followed_topics))
        )
    )

    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .where(
            and_(Shout.publishedAt.is_not(None), Shout.deletedAt.is_(None), Shout.id.in_(subquery))
        )
    )

    q = add_stat_columns(q)
    q = apply_filters(q, options.get("filters", {}), user_id)

    order_by = options.get("order_by", Shout.publishedAt)

    query_order_by = desc(order_by) if options.get("order_by_desc", True) else asc(order_by)
    offset = options.get("offset", 0)
    limit = options.get("limit", 10)

    q = q.group_by(Shout.id).order_by(nulls_last(query_order_by)).limit(limit).offset(offset)

    # print(q.compile(compile_kwargs={"literal_binds": True}))

    return get_shouts_from_query(q)
