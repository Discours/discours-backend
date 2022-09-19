import asyncio

from base.orm import local_session
from orm.shout import Shout, ShoutTopic
from orm.topic import TopicFollower
from services.zine.shoutauthor import ShoutAuthorStorage


class TopicStat:
    shouts_by_topic = {}  # Shout object stored
    authors_by_topic = {}  # User
    followers_by_topic = {}  # User
    lock = asyncio.Lock()
    period = 30 * 60  # sec

    @staticmethod
    async def load_stat(session):
        self = TopicStat
        shout_topics = session.query(ShoutTopic).all()
        print("[stat.topics] shouts linked %d times" % len(shout_topics))
        for shout_topic in shout_topics:
            tpc = shout_topic.topic
            # shouts by topics
            shout = session.query(Shout).where(Shout.slug == shout_topic.shout).first()
            self.shouts_by_topic[tpc] = self.shouts_by_topic.get(tpc, [])
            if shout not in self.shouts_by_topic[tpc]:
                self.shouts_by_topic[tpc].append(shout)

            # authors by topics
            authors = await ShoutAuthorStorage.get_authors(shout.slug)
            self.authors_by_topic[tpc] = self.authors_by_topic.get(tpc, [])
            for a in authors:
                if a not in self.authors_by_topic[tpc]:
                    self.authors_by_topic[tpc].append(a)

        print("[stat.topics] shouts indexed by %d topics" % len(self.shouts_by_topic.keys()))
        print("[stat.topics] authors indexed by %d topics" % len(self.authors_by_topic.keys()))

        self.followers_by_topic = {}
        followings = session.query(TopicFollower).all()
        for flw in followings:
            topic = flw.topic
            user = flw.follower
            self.followers_by_topic[topic] = self.followers_by_topic.get(topic, [])
            if user not in self.followers_by_topic[topic]:
                self.followers_by_topic[topic].append(user)
        print("[stat.topics] followers sorted")

    @staticmethod
    async def get_shouts(topic):
        self = TopicStat
        async with self.lock:
            return self.shouts_by_topic.get(topic, [])

    @staticmethod
    async def worker():
        self = TopicStat
        while True:
            try:
                with local_session() as session:
                    async with self.lock:
                        await self.load_stat(session)
            except Exception as err:
                raise Exception(err)
            await asyncio.sleep(self.period)
