import json
from datetime import datetime, timedelta

from sqlalchemy.orm import aliased, joinedload
from sqlalchemy.sql.expression import (
    and_,
    asc,
    case,
    desc,
    distinct,
    func,
    nulls_last,
    select,
)

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.exceptions import ObjectNotExist
from base.orm import local_session
from base.resolvers import query
from orm import TopicFollower
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.user import AuthorFollower
from resolvers.zine.topics import get_random_topic


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


# use_published_date is a quick fix, will be reworked as a part of tech debt
def apply_filters(q, filters, user_id=None, use_published_date=False):  # noqa: C901
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
        if use_published_date:
            q = q.filter(Shout.publishedAt >= date_from)
        else:
            q = q.filter(Shout.createdAt >= date_from)
    if filters.get("toDate"):
        # toDate: '2023-12-31'
        date_to = datetime.strptime(filters.get("toDate"), "%Y-%m-%d")
        if use_published_date:
            q = q.filter(Shout.publishedAt < (date_to + timedelta(days=1)))
        else:
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

    subquery = apply_filters(subquery, params.get("filters", {}), use_published_date=True)

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


@query.field("loadRandomTopicShouts")
async def load_random_topic_shouts(_, info, limit):
    topic = get_random_topic()

    q = (
        select(Shout)
        .options(
            joinedload(Shout.authors),
            joinedload(Shout.topics),
        )
        .join(ShoutTopic, and_(Shout.id == ShoutTopic.shout, ShoutTopic.topic == topic.id))
        .where(
            and_(Shout.deletedAt.is_(None), Shout.layout.is_not(None), Shout.visibility == "public")
        )
    )

    q = add_stat_columns(q)

    q = q.group_by(Shout.id).order_by(desc(Shout.createdAt)).limit(limit)

    shouts = get_shouts_from_query(q)

    return {"topic": topic, "shouts": shouts}


@query.field("loadUnratedShouts")
async def load_unrated_shouts(_, info, limit):
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id

    aliased_reaction = aliased(Reaction)

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
    )

    if user_id:
        q = q.outerjoin(
            aliased_reaction,
            and_(
                aliased_reaction.shout == Shout.id,
                aliased_reaction.replyTo.is_(None),
                aliased_reaction.kind.in_([ReactionKind.LIKE, ReactionKind.DISLIKE]),
                aliased_reaction.createdBy == user_id,
            ),
        )

    q = q.where(
        and_(
            Shout.deletedAt.is_(None),
            Shout.layout.is_not(None),
            Shout.createdAt >= (datetime.now() - timedelta(days=14)).date(),
        )
    )

    if user_id:
        q = q.where(Shout.createdBy != user_id)

    # 3 or fewer votes is 0, 1, 2 or 3 votes (null, reaction id1, reaction id2, reaction id3)
    q = q.having(func.count(distinct(Reaction.id)) <= 4)

    if user_id:
        q = q.having(func.count(distinct(aliased_reaction.id)) == 0)

    q = add_stat_columns(q)

    q = q.group_by(Shout.id).order_by(func.random()).limit(limit)

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
