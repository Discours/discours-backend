from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import asyncio

from services.zine.topics import TopicStorage

query_ackee_views = gql(
    """
    query getDomainsFacts {
        domains {
            statistics {
                views {
                    id
                    count
                }
                pages {
                    id
                    count
                    created
                }
            }
            facts {
                activeVisitors
                # averageViews
                # averageDuration
                viewsToday
                viewsMonth
                viewsYear
            }
        }
    }
    """
)


class Stat:
    lock = asyncio.Lock()
    by_slugs = {}
    by_topics = {}
    period = 30 * 60  # 30 minutes
    transport = AIOHTTPTransport(url="https://ackee.discours.io/")
    client = Client(transport=transport, fetch_schema_from_transport=True)

    @staticmethod
    async def load_views():
        # TODO: when the struture of paylod will be transparent
        # TODO: perhaps ackee token getting here

        self = Stat
        async with self.lock:
            domains = self.client.execute(query_ackee_views)
            print("[stat.ackee] loaded domains")
            print(domains)

            print('\n\n# TODO: something here...\n\n')

    @staticmethod
    async def get_shout(shout_slug):
        self = Stat
        async with self.lock:
            return self.by_slugs.get(shout_slug) or 0

    @staticmethod
    async def get_topic(topic_slug):
        self = Stat
        async with self.lock:
            shouts = self.by_topics.get(topic_slug)
            topic_views = 0
            for v in shouts.values():
                topic_views += v
            return topic_views

    @staticmethod
    async def increment(shout_slug, amount=1):
        self = Stat
        async with self.lock:
            self.by_slugs[shout_slug] = self.by_slugs.get(shout_slug) or 0
            self.by_slugs[shout_slug] += amount
            shout_topics = await TopicStorage.get_topics_by_slugs([shout_slug, ])
            for t in shout_topics:
                self.by_topics[t] = self.by_topics.get(t) or {}
                self.by_topics[t][shout_slug] = self.by_topics[t].get(shout_slug) or 0
                self.by_topics[t][shout_slug] += amount

    @staticmethod
    async def update():
        self = Stat
        async with self.lock:
            self.load_views()

    @staticmethod
    async def worker():
        while True:
            try:
                await Stat.update()
            except Exception as err:
                print("[stat.ackee] : %s" % (err))
            print("[stat.ackee] renew period: %d minutes" % (Stat.period / 60))
            await asyncio.sleep(Stat.period)
