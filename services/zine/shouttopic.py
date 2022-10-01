import asyncio

from base.orm import local_session
from orm.shout import ShoutTopic


class ShoutTopicStorage:
    topics_by_shout = {}
    lock = asyncio.Lock()
    period = 30 * 60  # sec

    @staticmethod
    async def load(session):
        self = ShoutTopicStorage
        sas = session.query(ShoutTopic).all()
        for sa in sas:
            self.topics_by_shout[sa.shout] = self.topics_by_shout.get(sa.shout, [])
            self.topics_by_shout[sa.shout].append([sa.user, sa.caption])
        print("[zine.topics] %d shouts preprocessed" % len(self.topics_by_shout))

    @staticmethod
    async def get_topics(shout):
        self = ShoutTopicStorage
        async with self.lock:
            return self.topics_by_shout.get(shout, [])

    @staticmethod
    async def worker():
        self = ShoutTopicStorage
        while True:
            try:
                with local_session() as session:
                    async with self.lock:
                        await self.load(session)
                        print("[zine.topics] state updated")
            except Exception as err:
                print("[zine.topics] errror: %s" % (err))
            await asyncio.sleep(self.period)
