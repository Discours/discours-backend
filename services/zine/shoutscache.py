import asyncio
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import selectinload

from base.orm import local_session
from orm.reaction import Reaction
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from services.stat.viewed import ViewedByDay, ViewedStorage
from services.stat.reacted import ReactedStorage


async def get_shout_stat(slug):
    return {
        "viewed": await ViewedStorage.get_shout(slug),
        "reacted": len(await ReactedStorage.get_shout(slug)),
        "commented": len(await ReactedStorage.get_comments(slug)),
        "rating": await ReactedStorage.get_rating(slug),
    }


async def prepare_shouts(session, stmt):
    shouts = []
    for s in list(map(lambda r: r.Shout, session.execute(stmt))):
        s.stat = await get_shout_stat(s.slug)
        shouts.append(s)
    return shouts


class ShoutsCache:
    limit = 200
    period = 60 * 60  # 1 hour
    lock = asyncio.Lock()

    recent_published = []
    recent_all = []
    recent_reacted = []
    recent_commented = []
    top_month = []
    top_overall = []
    top_viewed = []
    top_commented = []

    by_author = {}
    by_topic = {}

    @staticmethod
    async def prepare_recent_published():
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout)
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics)
                    )
                    .where(bool(Shout.publishedAt))
                    .filter(not bool(Shout.deletedAt))
                    .group_by(Shout.slug)
                    .order_by(desc(Shout.publishedAt))
                    .limit(ShoutsCache.limit)
                ),
            )
        async with ShoutsCache.lock:
            ShoutsCache.recent_published = shouts
            print("[zine.cache] %d recently published shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_all():
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout)
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics)
                    )
                    .filter(not bool(Shout.deletedAt))
                    .group_by(Shout.slug)
                    .order_by(desc(Shout.createdAt))
                    .limit(ShoutsCache.limit)
                ),
            )
        async with ShoutsCache.lock:
            ShoutsCache.recent_all = shouts
            print("[zine.cache] %d recently created shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_reacted():
        with local_session() as session:
            reactions = session.query(Reaction).order_by(Reaction.createdAt).limit(ShoutsCache.limit)
            reacted_slugs = set([])
            for r in reactions:
                reacted_slugs.add(r.shout)
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout)
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                    )
                    .where(Shout.slug.in_(list(reacted_slugs)))
                    .filter(not bool(Shout.deletedAt))
                    .group_by(Shout.slug)
                    .order_by(Shout.publishedAt)
                    .limit(ShoutsCache.limit)
                )
            )
            async with ShoutsCache.lock:
                ShoutsCache.recent_reacted = shouts
                print("[zine.cache] %d recently reacted shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_commented():
        with local_session() as session:
            reactions = session.query(Reaction).order_by(Reaction.createdAt).limit(ShoutsCache.limit)
            commented_slugs = set([])
            for r in reactions:
                if bool(r.body):
                    commented_slugs.add(r.shout)
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout)
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                    )
                    .where(Shout.slug.in_(list(commented_slugs)))
                    .filter(not bool(Shout.deletedAt))
                    .group_by(Shout.slug)
                    .order_by(Shout.publishedAt)
                    .limit(ShoutsCache.limit)
                )
            )
            async with ShoutsCache.lock:
                ShoutsCache.recent_commented = shouts
                print("[zine.cache] %d recently commented shouts " % len(shouts))

    @staticmethod
    async def prepare_top_overall():
        with local_session() as session:
            # with reacted times counter
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout, func.count(Reaction.id).label("reacted"))
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                        selectinload(Shout.reactions),
                    )
                    .join(Reaction)
                    .where(and_(bool(Shout.publishedAt), bool(Reaction.deletedAt)))
                    .group_by(Shout.slug)
                    .order_by(desc("reacted"))
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["rating"], reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top shouts " % len(shouts))
                ShoutsCache.top_overall = shouts

    @staticmethod
    async def prepare_top_month():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout, func.count(Reaction.id).label("reacted"))
                    .options(selectinload(Shout.authors), selectinload(Shout.topics))
                    .join(Reaction)
                    .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                    .group_by(Shout.slug)
                    .order_by(desc("reacted"))
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["rating"], reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top month shouts " % len(shouts))
                ShoutsCache.top_month = shouts

    @staticmethod
    async def prepare_top_commented():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout, Reaction)
                    .options(selectinload(Shout.authors), selectinload(Shout.topics))
                    .join(Reaction)
                    .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                    .group_by(Shout.slug)
                    .order_by(desc("commented"))
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["commented"], reverse=True)
        async with ShoutsCache.lock:
            print("[zine.cache] %d top commented shouts " % len(shouts))
            ShoutsCache.top_viewed = shouts

    @staticmethod
    async def prepare_top_viewed():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout, func.sum(ViewedByDay.value).label("viewed"))
                    .options(selectinload(Shout.authors), selectinload(Shout.topics))
                    .join(ViewedByDay)
                    .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                    .group_by(Shout.slug)
                    .order_by(desc("viewed"))
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["viewed"], reverse=True)
        async with ShoutsCache.lock:
            print("[zine.cache] %d top viewed shouts " % len(shouts))
            ShoutsCache.top_viewed = shouts

    @staticmethod
    async def prepare_by_author():
        shouts_by_author = {}
        with local_session() as session:
            for a in session.query(ShoutAuthor).all():
                shout = session.query(Shout).filter(Shout.slug == a.shout).first()
                shout.stat = await get_shout_stat(shout.slug)
                shouts_by_author[a.user] = shouts_by_author.get(a.user, [])
                if shout not in shouts_by_author[a.user]:
                    shouts_by_author[a.user].append(shout)
        async with ShoutsCache.lock:
            print("[zine.cache] indexed by %d authors " % len(shouts_by_author.keys()))
            ShoutsCache.by_author = shouts_by_author

    @staticmethod
    async def prepare_by_topic():
        shouts_by_topic = {}
        with local_session() as session:
            for a in session.query(ShoutTopic).all():
                shout = session.query(Shout).filter(Shout.slug == a.shout).first()
                shout.stat = await get_shout_stat(shout.slug)
                shouts_by_topic[a.topic] = shouts_by_topic.get(a.topic, [])
                if shout not in shouts_by_topic[a.topic]:
                    shouts_by_topic[a.topic].append(shout)
        async with ShoutsCache.lock:
            print("[zine.cache] indexed by %d topics " % len(shouts_by_topic.keys()))
            ShoutsCache.by_topic = shouts_by_topic

    @staticmethod
    async def worker():
        while True:
            try:
                await ShoutsCache.prepare_top_month()
                await ShoutsCache.prepare_top_overall()
                await ShoutsCache.prepare_top_viewed()

                await ShoutsCache.prepare_recent_published()
                await ShoutsCache.prepare_recent_all()
                await ShoutsCache.prepare_recent_reacted()
                await ShoutsCache.prepare_recent_commented()

                await ShoutsCache.prepare_by_author()
                await ShoutsCache.prepare_by_topic()
                print("[zine.cache] periodical update")
            except Exception as err:
                print("[zine.cache] error: %s" % (err))
                raise err
            await asyncio.sleep(ShoutsCache.period)
