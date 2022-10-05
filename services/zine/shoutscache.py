import asyncio
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import selectinload

from base.orm import local_session
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout
from services.stat.reacted import ReactedStorage


async def get_shout_stat(slug):
    return {
        # TODO: use ackee as datasource
        "viewed": 0,  # await ViewedStorage.get_shout(slug),
        "reacted": len(await ReactedStorage.get_shout(slug)),
        "commented": len(await ReactedStorage.get_comments(slug)),
        "rating": await ReactedStorage.get_rating(slug),
    }


async def prepare_shouts(session, stmt):
    shouts = []
    print(stmt)
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
                    .where(Shout.deletedAt.is_(None))
                    .filter(Shout.publishedAt.is_not(None))
                    .order_by(desc("publishedAt"))
                    .limit(ShoutsCache.limit)
                ),
            )
        async with ShoutsCache.lock:
            for s in shouts:
                for a in s.authors:
                    ShoutsCache.by_author[a.slug] = ShoutsCache.by_author.get(a.slug, {})
                    ShoutsCache.by_author[a.slug][s.slug] = s
                for t in s.topics:
                    ShoutsCache.by_topic[t.slug] = ShoutsCache.by_topic.get(t.slug, {})
                    ShoutsCache.by_topic[t.slug][s.slug] = s
            print("[zine.cache] indexed by %d topics " % len(ShoutsCache.by_topic.keys()))
            print("[zine.cache] indexed by %d authors " % len(ShoutsCache.by_author.keys()))
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
                    .where(Shout.deletedAt.is_(None))
                    .order_by(desc("createdAt"))
                    .limit(ShoutsCache.limit)
                )
            )
        async with ShoutsCache.lock:
            ShoutsCache.recent_all = shouts[0:ShoutsCache.limit]
            print("[zine.cache] %d recently created shouts " % len(ShoutsCache.recent_all))

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
                    select(
                        Shout,
                        Reaction.createdAt.label('reactedAt')
                    )
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                        selectinload(Shout.reactions),
                    )
                    .join(Reaction)
                    .where(and_(Shout.deletedAt.is_(None), Shout.slug.in_(reacted_slugs)))
                    .filter(Shout.publishedAt.is_not(None))
                    .group_by(Shout.slug, "reactedAt")
                    .order_by(desc("reactedAt"))
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
                if len(r.body) > 0:
                    commented_slugs.add(r.shout)
            shouts = await prepare_shouts(
                session,
                (
                    select(
                        Shout,
                        Reaction.createdAt.label('reactedAt')
                    )
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                        selectinload(Shout.reactions),
                    )
                    .join(Reaction)
                    .where(and_(Shout.deletedAt.is_(None), Shout.slug.in_(commented_slugs)))
                    .group_by(Shout.slug, "reactedAt")
                    .order_by(desc("reactedAt"))
                    .limit(ShoutsCache.limit)
                )
            )
            async with ShoutsCache.lock:
                ShoutsCache.recent_commented = shouts
                print("[zine.cache] %d recently commented shouts " % len(shouts))

    @staticmethod
    async def prepare_top_overall():
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(
                        Shout,
                        func.sum(Reaction.id).label('reacted')
                    )
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                        selectinload(Shout.reactions),
                    )
                    .join(Reaction, Reaction.kind == ReactionKind.LIKE)
                    .where(Shout.deletedAt.is_(None))
                    .filter(Shout.publishedAt.is_not(None))
                    .group_by(Shout.slug)
                    .order_by(desc("reacted"))
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["rating"], reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top rated published " % len(shouts))
                ShoutsCache.top_overall = shouts

    @staticmethod
    async def prepare_top_month():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(Shout)
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                        selectinload(Shout.reactions),
                    )
                    .join(Reaction)
                    .where(Shout.deletedAt.is_(None))
                    .filter(Shout.publishedAt > month_ago)
                    .group_by(Shout.slug)
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["rating"], reverse=True)
            async with ShoutsCache.lock:
                ShoutsCache.top_month = shouts
                print("[zine.cache] %d top month published " % len(ShoutsCache.top_month))

    @staticmethod
    async def prepare_top_commented():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(
                session,
                (
                    select(
                        Shout,
                        func.sum(Reaction.id).label("commented")
                    )
                    .options(
                        selectinload(Shout.authors),
                        selectinload(Shout.topics),
                        selectinload(Shout.reactions)
                    )
                    .join(Reaction, func.length(Reaction.body) > 0)
                    .where(Shout.deletedAt.is_(None))
                    .filter(Shout.publishedAt > month_ago)
                    .group_by(Shout.slug)
                    .order_by(desc("commented"))
                    .limit(ShoutsCache.limit)
                ),
            )
            shouts.sort(key=lambda s: s.stat["commented"], reverse=True)
        async with ShoutsCache.lock:
            ShoutsCache.top_commented = shouts
            print("[zine.cache] %d last month top commented shouts " % len(ShoutsCache.top_commented))

    @staticmethod
    async def get_top_published_before(daysago, offset, limit):
        shouts_by_rating = []
        before = datetime.now() - timedelta(days=daysago)
        for s in ShoutsCache.recent_published:
            if s.publishedAt >= before:
                shouts_by_rating.append(s)
        shouts_by_rating.sort(lambda s: s.stat["rating"], reverse=True)
        return shouts_by_rating

    @staticmethod
    async def worker():
        while True:
            try:
                await ShoutsCache.prepare_top_month()
                await ShoutsCache.prepare_top_overall()
                await ShoutsCache.prepare_top_commented()

                await ShoutsCache.prepare_recent_published()
                await ShoutsCache.prepare_recent_all()
                await ShoutsCache.prepare_recent_reacted()
                await ShoutsCache.prepare_recent_commented()
                print("[zine.cache] periodical update")
            except Exception as err:
                print("[zine.cache] error: %s" % (err))
                raise err
            await asyncio.sleep(ShoutsCache.period)
