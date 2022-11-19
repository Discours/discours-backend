import asyncio
from orm.topic import Topic


class TopicStorage:
    topics = {}
    lock = asyncio.Lock()

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
