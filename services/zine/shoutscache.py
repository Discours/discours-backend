import asyncio
from datetime import datetime, timedelta
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import selectinload
from base.orm import local_session
from orm.reaction import Reaction
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedByDay


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
            stmt = (
                select(Shout)
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .where(bool(Shout.publishedAt))
                .order_by(desc("publishedAt"))
                .limit(ShoutsCache.limit)
            )
            shouts = []
            for row in session.execute(stmt):
                shout = row.Shout
                shout.rating = await ReactedStorage.get_rating(shout.slug) or 0
                shouts.append(shout)
        async with ShoutsCache.lock:
            ShoutsCache.recent_published = shouts
            print("[zine.cache] %d recently published shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_all():
        with local_session() as session:
            stmt = (
                select(Shout)
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .order_by(desc("createdAt"))
                .limit(ShoutsCache.limit)
            )
            shouts = []
            for row in session.execute(stmt):
                shout = row.Shout
                # shout.topics = [t.slug for t in shout.topics]
                shout.rating = await ReactedStorage.get_rating(shout.slug) or 0
                shouts.append(shout)
        async with ShoutsCache.lock:
            ShoutsCache.recent_all = shouts
            print("[zine.cache] %d recently created shouts " % len(shouts))

    @staticmethod
    async def prepare_recent_reacted():
        with local_session() as session:
            stmt = (
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
            )
            shouts = []
            for row in session.execute(stmt):
                shout = row.Shout
                # shout.topics = [t.slug for t in shout.topics]
                shout.rating = await ReactedStorage.get_rating(shout.slug) or 0
                shouts.append(shout)
            async with ShoutsCache.lock:
                ShoutsCache.recent_reacted = shouts
                print("[zine.cache] %d recently reacted shouts " % len(shouts))

    @staticmethod
    async def prepare_top_overall():
        with local_session() as session:
            # with reacted times counter
            stmt = (
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
            )
            shouts = []
            # with rating synthetic counter
            for row in session.execute(stmt):
                shout = row.Shout
                shout.rating = await ReactedStorage.get_rating(shout.slug) or 0
                shouts.append(shout)
            shouts.sort(key=lambda shout: shout.rating, reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top shouts " % len(shouts))
                ShoutsCache.top_overall = shouts

    @staticmethod
    async def prepare_top_month():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            stmt = (
                select(Shout, func.count(Reaction.id).label("reacted"))
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .join(Reaction)
                .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                .group_by(Shout.slug)
                .order_by(desc("reacted"))
                .limit(ShoutsCache.limit)
            )
            shouts = []
            for row in session.execute(stmt):
                shout = row.Shout
                shout.rating = await ReactedStorage.get_rating(shout.slug) or 0
                shouts.append(shout)
            shouts.sort(key=lambda shout: shout.rating, reverse=True)
            async with ShoutsCache.lock:
                print("[zine.cache] %d top month shouts " % len(shouts))
                ShoutsCache.top_month = shouts

    @staticmethod
    async def prepare_top_viewed():
        month_ago = datetime.now() - timedelta(days=30)
        with local_session() as session:
            stmt = (
                select(Shout, func.sum(ViewedByDay.value).label("viewed"))
                .options(selectinload(Shout.authors), selectinload(Shout.topics))
                .join(ViewedByDay)
                .where(and_(Shout.createdAt > month_ago, bool(Reaction.deletedAt)))
                .group_by(Shout.slug)
                .order_by(desc("viewed"))
                .limit(ShoutsCache.limit)
            )
            shouts = []
            for row in session.execute(stmt):
                shout = row.Shout
                shout.rating = await ReactedStorage.get_rating(shout.slug) or 0
                shouts.append(shout)
        # shouts.sort(key = lambda shout: shout.viewed, reverse = True)
        async with ShoutsCache.lock:
            print("[zine.cache] %d top viewed shouts " % len(shouts))
            ShoutsCache.top_viewed = shouts

    @staticmethod
    async def prepare_by_author():
        shouts_by_author = {}
        with local_session() as session:

            for a in session.query(ShoutAuthor).all():

                shout = session.query(Shout).filter(Shout.slug == a.shout).first()

                if not shouts_by_author[a.author]:
                    shouts_by_author[a.author] = []

                if shout not in shouts_by_author[a.author]:
                    shouts_by_author[a.author].push(shout)
        async with ShoutsCache.lock:
            print("[zine.cache indexed by %d authors " % len(shouts_by_author.keys()))
            ShoutsCache.by_author = shouts_by_author

    @staticmethod
    async def prepare_by_topic():
        shouts_by_topic = {}
        with local_session() as session:

            for t in session.query(ShoutTopic).all():

                shout = session.query(Shout).filter(Shout.slug == t.shout).first()

                if not shouts_by_topic[t.topic]:
                    shouts_by_topic[t.topic] = []

                if shout not in shouts_by_topic[t.topic]:
                    shouts_by_topic[t.topic].push(shout)
        async with ShoutsCache.lock:
            print("[zine.cache] indexed by %d topics " % len(shouts_by_topic.keys()))
            ShoutsCache.by_topic = shouts_by_topic

    @staticmethod
    async def get_shouts_by_author():
        async with ShoutsCache.lock:
            return ShoutsCache.by_author

    @staticmethod
    async def get_shouts_by_topic():
        async with ShoutsCache.lock:
            return ShoutsCache.by_topic

    @staticmethod
    async def get_top_overall():
        async with ShoutsCache.lock:
            return ShoutsCache.by_topic

    @staticmethod
    async def get_top_month():
        async with ShoutsCache.lock:
            return ShoutsCache.by_topic

    @staticmethod
    async def get_top_viewed():
        async with ShoutsCache.lock:
            return ShoutsCache.by_topic

    @staticmethod
    async def get_recent_published():
        async with ShoutsCache.lock:
            return ShoutsCache.recent_published

    @staticmethod
    async def get_recent_all():
        async with ShoutsCache.lock:
            return ShoutsCache.recent_all

    @staticmethod
    async def get_recent_reacted():
        async with ShoutsCache.lock:
            return ShoutsCache.recent_reacted

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
