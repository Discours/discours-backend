import asyncio
from base.orm import local_session
from orm.shout import Shout
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage
from services.zine.shoutauthor import ShoutAuthorStorage
from orm.topic import ShoutTopic, TopicFollower


def unique(list1):

    # insert the list to the set
    list_set = set(list1)
    # convert the set to the list
    unique_list = (list(list_set))
    return unique_list


class TopicStat:
    shouts_by_topic = {}
    authors_by_topic = {}
    followers_by_topic = {}
    lock = asyncio.Lock()
    period = 30 * 60  # sec

    @staticmethod
    async def load_stat(session):
        self = TopicStat
        shout_topics = session.query(ShoutTopic).all()
        print('[stat.topics] shout topics amount', len(shout_topics))
        for shout_topic in shout_topics:

            # shouts by topics
            topic = shout_topic.topic
            shout = shout_topic.shout
            sss = set(self.shouts_by_topic.get(topic, []))
            shout = session.query(Shout).where(Shout.slug == shout).first()
            sss.union([shout, ])
            self.shouts_by_topic[topic] = list(sss)

            # authors by topics
            authors = await ShoutAuthorStorage.get_authors(shout)
            aaa = set(self.authors_by_topic.get(topic, []))
            aaa.union(authors)
            self.authors_by_topic[topic] = list(aaa)

        print("[stat.topics] authors sorted")
        print("[stat.topics] shouts sorted")

        self.followers_by_topic = {}
        followings = session.query(TopicFollower)
        for flw in followings:
            topic = flw.topic
            user = flw.follower
            if topic not in self.followers_by_topic:
                self.followers_by_topic[topic] = []
            self.followers_by_topic[topic].append(user)
        print("[stat.topics] followers sorted")

    @staticmethod
    async def get_shouts(topic):
        self = TopicStat
        async with self.lock:
            return self.shouts_by_topic.get(topic, [])

    @staticmethod
    async def get_stat(topic):
        self = TopicStat
        async with self.lock:
            shouts = self.shouts_by_topic.get(topic, [])
            followers = self.followers_by_topic.get(topic, [])
            authors = self.authors_by_topic.get(topic, [])

        return {
            "shouts": len(shouts),
            "authors": len(authors),
            "followers": len(followers),
            "viewed": await ViewedStorage.get_topic(topic),
            "reacted": len(await ReactedStorage.get_topic(topic)),
            "commented": len(await ReactedStorage.get_topic_comments(topic)),
            "rating": await ReactedStorage.get_topic_rating(topic),
        }

    @staticmethod
    async def worker():
        self = TopicStat
        while True:
            try:
                with local_session() as session:
                    async with self.lock:
                        await self.load_stat(session)
                        print("[stat.topics] periodical update")
            except Exception as err:
                print("[stat.topics] errror: %s" % (err))
            await asyncio.sleep(self.period)
