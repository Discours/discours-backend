import asyncio
from datetime import datetime, timedelta
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import selectinload
from base.orm import local_session
from orm.reaction import Reaction
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from services.stat.viewed import ViewedByDay


async def prepare_shouts(session, stmt):
    shouts = []
    for s in list(map(lambda r: r.Shout, session.execute(stmt))):
        s.stats = await s.stat
        shouts.append(s)
    return shouts


class ShoutsCache:
    limit = 200
    period = 60 * 60  # 1 hour
    lock = asyncio.Lock()

    recent_published = []
    recent_all = []
    recent_reacted = []
    top_month = []
    top_overall = []
    top_viewed = []

    by_author = {}
    by_topic = {}

    @staticmethod
    async def prepare_recent_published():
        with local_session() as session:
            shouts = await prepare_shouts(session, (
                select(Shout)
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .where(bool(Shout.publishedAt))
                .order_by(desc("publishedAt"))
                .order_by(desc("createdAt"))
                .limit(ShoutsCache.limit)
            ))
        async with ShoutsCache.lock:
            ShoutsCache.recent_published = shouts
            print("[zine.cache] %d recently published shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_all():
        with local_session() as session:
            shouts = await prepare_shouts(session, (
                select(Shout)
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .order_by(desc("createdAt"))
                .limit(ShoutsCache.limit)
            ))
        async with ShoutsCache.lock:
            ShoutsCache.recent_all = shouts
            print("[zine.cache] %d recently created shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_reacted():
        with local_session() as session:
            shouts = await prepare_shouts(session, (
                select(Shout, func.max(Reaction.createdAt).label("reactionCreatedAt"))
                .options(
                    selectinload(Shout.authors),
                    selectinload(Shout.topics),
                )
                .join(Reaction, Reaction.shout == Shout.slug)
                .where(and_(bool(Shout.publishedAt), bool(Reaction.deletedAt)))
                .group_by(Shout.slug)
                .order_by(desc("reactionCreatedAt"))
                .limit(ShoutsCache.limit)
            ))
            async with ShoutsCache.lock:
                ShoutsCache.recent_reacted = shouts
                print("[zine.cache] %d recently reacted shouts " % len(shouts))

    @staticmethod
    async def prepare_top_overall():
        with local_session() as session:
            # with reacted times counter
            shouts = await prepare_shouts(session, (
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
            ))
            shouts.sort(key=lambda s: s.stats['rating'], reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top shouts " % len(shouts))
                ShoutsCache.top_overall = shouts

    @staticmethod
    async def prepare_top_month():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(session, (
                select(Shout, func.count(Reaction.id).label("reacted"))
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .join(Reaction)
                .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                .group_by(Shout.slug)
                .order_by(desc("reacted"))
                .limit(ShoutsCache.limit)
            ))
            shouts.sort(key=lambda s: s.stats['rating'], reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top month shouts " % len(shouts))
                ShoutsCache.top_month = shouts

    @staticmethod
    async def prepare_top_viewed():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            shouts = await prepare_shouts(session, (
                select(Shout, func.sum(ViewedByDay.value).label("viewed"))
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .join(ViewedByDay)
                .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                .group_by(Shout.slug)
                .order_by(desc("viewed"))
                .limit(ShoutsCache.limit)
            ))
            shouts.sort(key=lambda s: s.stats['viewed'], reverse=True)
        async with ShoutsCache.lock:
            print("[zine.cache] %d top viewed shouts " % len(shouts))
            ShoutsCache.top_viewed = shouts

    @staticmethod
    async def prepare_by_author():
        shouts_by_author = {}
        with local_session() as session:

            for a in session.query(ShoutAuthor).all():

                shout = session.query(Shout).filter(Shout.slug == a.shout).first()

                if not shouts_by_author.get(a.user):
                    shouts_by_author[a.user] = []

                if shout not in shouts_by_author[a.user]:
                    shouts_by_author[a.user].append(shout)
        async with ShoutsCache.lock:
            print("[zine.cache] indexed by %d authors " % len(shouts_by_author.keys()))
            ShoutsCache.by_author = shouts_by_author

    @staticmethod
    async def prepare_by_topic():
        shouts_by_topic = {}
        with local_session() as session:

            for t in session.query(ShoutTopic).all():

                shout = session.query(Shout).filter(Shout.slug == t.shout).first()

                if not shouts_by_topic.get(t.topic):
                    shouts_by_topic[t.topic] = []

                if shout not in shouts_by_topic[t.topic]:
                    shouts_by_topic[t.topic].append(shout)

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

                await ShoutsCache.prepare_by_author()
                await ShoutsCache.prepare_by_topic()
                print("[zine.cache] periodical update")
            except Exception as err:
                print("[zine.cache] error: %s" % (err))
                raise err
            await asyncio.sleep(ShoutsCache.period)
