import asyncio
from base.orm import local_session
from orm.topic import Topic
from orm.shout import Shout
import sqlalchemy as sa
from sqlalchemy import select


class TopicStorage:
    topics = {}
    lock = asyncio.Lock()
    random_topics = []

    @staticmethod
    def init(session):
        self = TopicStorage
        topics = session.query(Topic)
        self.topics = dict([(topic.slug, topic) for topic in topics])
        for tpc in self.topics.values():
            # self.load_parents(tpc)
            pass

        print("[zine.topics] %d precached" % len(self.topics.keys()))

    # @staticmethod
    # def load_parents(topic):
    #     self = TopicStorage
    #     parents = []
    #     for parent in self.topics.values():
    #         if topic.slug in parent.children:
    #             parents.append(parent.slug)
    #     topic.parents = parents
    #     return topic

    @staticmethod
    def get_random_topics(amount):
        return TopicStorage.random_topics[0:amount]

    @staticmethod
    def renew_topics_random():
        with local_session() as session:
            q = select(Topic).join(Shout).group_by(Topic.id).having(sa.func.count(Shout.id) > 2).order_by(
                sa.func.random()).limit(50)
            TopicStorage.random_topics = list(map(
                lambda result_item: result_item.Topic, session.execute(q)
            ))

    @staticmethod
    async def worker():
        self = TopicStorage
        async with self.lock:
            while True:
                try:
                    self.renew_topics_random()
                except Exception as err:
                    print("[zine.topics] error %s" % (err))
                await asyncio.sleep(300)  # 5 mins

    @staticmethod
    async def get_topics_all():
        self = TopicStorage
        async with self.lock:
            return list(self.topics.values())

    @staticmethod
    async def get_topics_by_slugs(slugs):
        self = TopicStorage
        async with self.lock:
            if not slugs:
                return self.topics.values()
            topics = filter(lambda topic: topic.slug in slugs, self.topics.values())
            return list(topics)

    @staticmethod
    async def get_topics_by_community(community):
        self = TopicStorage
        async with self.lock:
            topics = filter(
                lambda topic: topic.community == community, self.topics.values()
            )
            return list(topics)

    @staticmethod
    async def get_topics_by_author(author):
        self = TopicStorage
        async with self.lock:
            topics = filter(
                lambda topic: topic.community == author, self.topics.values()
            )
            return list(topics)

    @staticmethod
    async def update_topic(topic):
        self = TopicStorage
        async with self.lock:
            self.topics[topic.slug] = topic
            # self.load_parents(topic)
