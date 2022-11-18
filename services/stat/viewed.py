import asyncio

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

from base.orm import local_session
from orm.viewed import ViewedEntry
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


class ViewedStorage:
    lock = asyncio.Lock()
    by_topics = {}
    period = 5 * 60  # 5 minutes
    client = None
    transport = None

    @staticmethod
    async def load_views(session):
        # TODO: when the struture of payload will be transparent
        # TODO: perhaps ackee token getting here

        self = ViewedStorage()
        async with self.lock:
            self.transport = AIOHTTPTransport(url="https://ackee.discours.io/", ssl=ssl)
            self.client = Client(transport=self.transport, fetch_schema_from_transport=True)
            domains = await self.client.execute_async(query_ackee_views)
            print("[stat.ackee] loaded domains")
            print(domains)
            print('\n\n# TODO: something here...\n\n')

    @staticmethod
    async def increment(shout_slug, amount=1, viewer='anonymous'):
        self = ViewedStorage
        async with self.lock:
            with local_session() as session:
                viewed = ViewedEntry.create({
                    "viewer": viewer,
                    "shout": shout_slug
                })
                session.add(viewed)
                session.commit()

                shout_topics = await TopicStorage.get_topics_by_slugs([shout_slug, ])
                for t in shout_topics:
                    self.by_topics[t] = self.by_topics.get(t) or {}
                    self.by_topics[t][shout_slug] = self.by_topics[t].get(shout_slug) or 0
                    self.by_topics[t][shout_slug] += amount

    @staticmethod
    async def worker():
        self = ViewedStorage
        while True:
            try:
                with local_session() as session:
                    await self.load_views(session)
            except Exception as err:
                print("[stat.viewed] : %s" % (err))
            print("[stat.viewed] renew period: %d minutes" % (self.period / 60))
            await asyncio.sleep(self.period)
