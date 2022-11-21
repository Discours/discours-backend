import asyncio

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from base.orm import local_session
from sqlalchemy import func, select
from orm.shout import ShoutTopic
from orm.viewed import ViewedEntry
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
    by_shouts = {}
    by_topics = {}
    period = 5 * 60  # 5 minutes
    client = None
    transport = None

    @staticmethod
    def init():
        ViewedStorage.transport = AIOHTTPTransport(url="https://ackee.discours.io/", ssl=ssl)
        ViewedStorage.client = Client(transport=ViewedStorage.transport, fetch_schema_from_transport=True)

    @staticmethod
    async def update_views(session):
        # TODO: when the struture of payload will be transparent
        # TODO: perhaps ackee token getting here

        self = ViewedStorage
        async with self.lock:
            domains = await self.client.execute_async(query_ackee_views)
            print("[stat.ackee] loaded domains")
            print(domains)
            print('\n\n# TODO: something here...\n\n')

    @staticmethod
    async def get_shout(shout_slug):
        self = ViewedStorage
        async with self.lock:
            r = self.by_shouts.get(shout_slug)
            if not r:
                with local_session() as session:
                    shout_views = 0
                    shout_views_q = select(func.sum(ViewedEntry.amount)).where(
                        ViewedEntry.shout == shout_slug
                    )
                    shout_views = session.execute(shout_views_q)
                    self.by_shouts[shout_slug] = shout_views
                    return shout_views
            else:
                return r

    @staticmethod
    async def get_topic(topic_slug):
        self = ViewedStorage
        topic_views = 0
        async with self.lock:
            topic_views_by_shouts = self.by_topics.get(topic_slug) or {}
            for shout in topic_views_by_shouts:
                topic_views += shout
        return topic_views

    @staticmethod
    async def increment(shout_slug, amount=1, viewer='anonymous'):
        self = ViewedStorage
        async with self.lock:
            with local_session() as session:
                viewed = ViewedEntry.create(**{
                    "viewer": viewer,
                    "shout": shout_slug,
                    "amount": amount
                })
                session.add(viewed)
                session.commit()
                self.by_shouts[shout_slug] = self.by_shouts.get(shout_slug, 0) + amount
                topics = session.query(ShoutTopic).where(ShoutTopic.shout == shout_slug).all()
                for t in topics:
                    tpc = t.topic
                    if not self.by_topics.get(tpc):
                        self.by_topics[tpc] = {}
                    self.by_topics[tpc][shout_slug] = self.by_shouts[shout_slug]

    @staticmethod
    async def worker():
        self = ViewedStorage
        while True:
            try:
                with local_session() as session:
                    await self.update_views(session)
                    print("[stat.viewed] next renew in %d minutes" % (self.period / 60))
            except Exception as err:
                print("[stat.viewed] %s" % (err))
            await asyncio.sleep(self.period)
