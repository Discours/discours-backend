from orm.collection import ShoutCollection
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from base.orm import local_session
from base.resolvers import mutation, query
from services.zine.shoutauthor import ShoutAuthorStorage
from services.zine.shoutscache import ShoutsCache
from services.stat.viewed import ViewedStorage
from resolvers.profile import author_follow, author_unfollow
from resolvers.topics import topic_follow, topic_unfollow
from resolvers.community import community_follow, community_unfollow
from resolvers.reactions import reactions_follow, reactions_unfollow
from auth.authenticate import login_required
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import selectinload


@query.field("topViewed")
async def top_viewed(_, _info, page, size):
    async with ShoutsCache.lock:
        return ShoutsCache.top_viewed[((page - 1) * size) : (page * size)]


@query.field("topMonth")
async def top_month(_, _info, page, size):
    async with ShoutsCache.lock:
        return ShoutsCache.top_month[((page - 1) * size) : (page * size)]


@query.field("topOverall")
async def top_overall(_, _info, page, size):
    async with ShoutsCache.lock:
        return ShoutsCache.top_overall[((page - 1) * size) : (page * size)]


@query.field("recentPublished")
async def recent_published(_, _info, page, size):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_published[((page - 1) * size) : (page * size)]


@query.field("recentAll")
async def recent_all(_, _info, page, size):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_all[((page - 1) * size) : (page * size)]


@query.field("recentReacted")
async def recent_reacted(_, _info, page, size):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_reacted[((page - 1) * size) : (page * size)]


@mutation.field("viewShout")
async def view_shout(_, _info, slug):
    await ViewedStorage.increment(slug)
    return {"error": ""}


@query.field("getShoutBySlug")
async def get_shout_by_slug(_, info, slug):
    all_fields = [
        node.name.value for node in info.field_nodes[0].selection_set.selections
    ]
    selected_fields = set(["authors", "topics"]).intersection(all_fields)
    select_options = [selectinload(getattr(Shout, field)) for field in selected_fields]
    shout = {}
    with local_session() as session:
        # s = text(open("src/queries/shout-by-slug.sql", "r").read() % slug)
        shout = (
            session.query(Shout)
            .options(select_options)
            .filter(Shout.slug == slug)
            .first()
        )

        if not shout:
            print(f"shout with slug {slug} not exist")
            return {"error": "shout not found"}
        else:
            for a in shout.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(slug, a.slug)
    return shout


@query.field("searchQuery")
async def get_search_results(_, _info, query, page, size):
    # TODO: remove the copy of searchByTopics
    # with search ranking query
    page = page - 1
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutTopic)
            .where(and_(ShoutTopic.topic.in_(query), bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(size)
            .offset(page * size)
        )

    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
        s.stat.search = 1  # FIXME
    return shouts


@query.field("shoutsByTopics")
async def shouts_by_topics(_, _info, slugs, page, size):
    page = page - 1
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutTopic)
            .where(and_(ShoutTopic.topic.in_(slugs), bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(size)
            .offset(page * size)
        )

    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
    return shouts


@query.field("shoutsByCollection")
async def shouts_by_collection(_, _info, collection, page, size):
    page = page - 1
    shouts = []
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutCollection, ShoutCollection.collection == collection)
            .where(and_(ShoutCollection.shout == Shout.slug, bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(size)
            .offset(page * size)
        )
    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
    return shouts


@query.field("shoutsByAuthors")
async def shouts_by_authors(_, _info, slugs, page, size):
    page = page - 1
    with local_session() as session:

        shouts = (
            session.query(Shout)
            .join(ShoutAuthor)
            .where(and_(ShoutAuthor.user.in_(slugs), bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(size)
            .offset(page * size)
        )

    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
    return shouts


SINGLE_COMMUNITY = True


@query.field("shoutsByCommunities")
async def shouts_by_communities(_, info, slugs, page, size):
    if SINGLE_COMMUNITY:
        return recent_published(_, info, page, size)
    else:
        page = page - 1
        with local_session() as session:
            # TODO fix postgres high load
            shouts = (
                session.query(Shout)
                .distinct()
                .join(ShoutTopic)
                .where(
                    and_(
                        bool(Shout.publishedAt),
                        ShoutTopic.topic.in_(
                            select(Topic.slug).where(Topic.community.in_(slugs))
                        ),
                    )
                )
                .order_by(desc(Shout.publishedAt))
                .limit(size)
                .offset(page * size)
            )

        for s in shouts:
            for a in s.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
        return shouts


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    user = info.context["request"].user
    try:
        if what == "AUTHOR":
            author_follow(user, slug)
        elif what == "TOPIC":
            topic_follow(user, slug)
        elif what == "COMMUNITY":
            community_follow(user, slug)
        elif what == "REACTIONS":
            reactions_follow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    user = info.context["request"].user

    try:
        if what == "AUTHOR":
            author_unfollow(user, slug)
        elif what == "TOPIC":
            topic_unfollow(user, slug)
        elif what == "COMMUNITY":
            community_unfollow(user, slug)
        elif what == "REACTIONS":
            reactions_unfollow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}
