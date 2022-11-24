import asyncio
import time
from base.orm import local_session
from orm.shout import Shout, ShoutTopic, ShoutAuthor
from orm.topic import TopicFollower
from sqlalchemy.sql.expression import select


class TopicStat:
    # by slugs
    shouts_by_topic = {}  # Shout object stored
    authors_by_topic = {}  # User
    followers_by_topic = {}  # User
    #
    lock = asyncio.Lock()
    period = 30 * 60  # sec

    @staticmethod
    async def load_stat(session):
        start = time.time()
        self = TopicStat
        shout_topics = session.query(ShoutTopic, Shout).join(Shout).all()
        all_shout_authors = session.query(ShoutAuthor).all()
        print("[stat.topics] %d links for shouts" % len(shout_topics))
        for [shout_topic, shout] in shout_topics:
            tpc = shout_topic.topic
            # shouts by topics
            # shout = session.query(Shout).where(Shout.slug == shout_topic.shout).first()
            self.shouts_by_topic[tpc] = self.shouts_by_topic.get(tpc, dict())
            self.shouts_by_topic[tpc][shout.slug] = shout

            # authors by topics
            shout_authors = filter(lambda asa: asa.shout == shout.slug, all_shout_authors)

            self.authors_by_topic[tpc] = self.authors_by_topic.get(tpc, dict())
            for sa in shout_authors:
                self.authors_by_topic[tpc][sa.shout] = sa.caption

        self.followers_by_topic = {}
        followings = session.query(TopicFollower).all()
        print("[stat.topics] %d followings by users" % len(followings))
        for flw in followings:
            topic = flw.topic
            userslug = flw.follower
            self.followers_by_topic[topic] = self.followers_by_topic.get(topic, dict())
            self.followers_by_topic[topic][userslug] = userslug

        end = time.time()
        print("[stat.topics] load_stat took %fs " % (end - start))

    @staticmethod
    async def get_shouts(topic):
        self = TopicStat
        async with self.lock:
            return self.shouts_by_topic.get(topic, dict())

    @staticmethod
    async def worker():
        self = TopicStat
        first_run = True
        while True:
            try:
                with local_session() as session:
                    async with self.lock:
                        await self.load_stat(session)
            except Exception as err:
                raise Exception(err)
            if first_run:
                # sleep for period + 1 min after first run
                # to distribute load on server by workers with the same period
                await asyncio.sleep(60)
                first_run = False
            await asyncio.sleep(self.period)
