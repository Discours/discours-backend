import asyncio
import json

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

from base.redis import redis
from services.zine.topics import TopicStorage
from ssl import create_default_context


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

ssl = create_default_context()


class ViewStat:
    lock = asyncio.Lock()
    by_slugs = {}
    by_topics = {}
    period = 5 * 60  # 5 minutes
    transport = AIOHTTPTransport(url="https://ackee.discours.io/", ssl=ssl)
    client = Client(transport=transport, fetch_schema_from_transport=True)

    @staticmethod
    async def load_views():
        # TODO: when the struture of paylod will be transparent
        # TODO: perhaps ackee token getting here

        self = ViewStat
        async with self.lock:
            self.by_topics = await redis.execute("GET", "views_by_topics")
            if self.by_topics:
                self.by_topics = dict(json.loads(self.by_topics))
            else:
                self.by_topics = {}
            self.by_slugs = await redis.execute("GET", "views_by_shouts")
            if self.by_slugs:
                self.by_slugs = dict(json.loads(self.by_slugs))
            else:
                self.by_slugs = {}
            domains = await self.client.execute_async(query_ackee_views)
            print("[stat.ackee] loaded domains")
            print(domains)

            print('\n\n# TODO: something here...\n\n')

    @staticmethod
    async def get_shout(shout_slug):
        self = ViewStat
        async with self.lock:
            return self.by_slugs.get(shout_slug) or 0

    @staticmethod
    async def get_topic(topic_slug):
        self = ViewStat
        async with self.lock:
            shouts = self.by_topics.get(topic_slug) or {}
            topic_views = 0
            for v in shouts.values():
                topic_views += v
            return topic_views

    @staticmethod
    async def increment(shout_slug, amount=1):
        self = ViewStat
        async with self.lock:
            self.by_slugs[shout_slug] = self.by_slugs.get(shout_slug) or 0
            self.by_slugs[shout_slug] += amount
            await redis.execute(
                "SET",
                f"views_by_shouts/{shout_slug}",
                str(self.by_slugs[shout_slug])
            )
            shout_topics = await TopicStorage.get_topics_by_slugs([shout_slug, ])
            for t in shout_topics:
                self.by_topics[t] = self.by_topics.get(t) or {}
                self.by_topics[t][shout_slug] = self.by_topics[t].get(shout_slug) or 0
                self.by_topics[t][shout_slug] += amount
                await redis.execute(
                    "SET",
                    f"views_by_topics/{t}/{shout_slug}",
                    str(self.by_topics[t][shout_slug])
                )

    @staticmethod
    async def reset():
        self = ViewStat
        self.by_topics = {}
        self.by_slugs = {}

    @staticmethod
    async def worker():
        self = ViewStat
        while True:
            try:
                await self.load_views()
            except Exception as err:
                print("[stat.ackee] : %s" % (err))
            print("[stat.ackee] renew period: %d minutes" % (ViewStat.period / 60))
            await asyncio.sleep(self.period)
