import asyncio
from datetime import timedelta, timezone, datetime
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from base.orm import local_session
from sqlalchemy import func, select
from orm.shout import ShoutTopic
from orm.viewed import ViewedEntry
from ssl import create_default_context
from os import environ, path


domain = environ.get("ACKEE_DOMAIN") or "1004abeb-89b2-4e85-ad97-74f8d2c8ed2d"

login_mutation = gql("""
    mutation createToken($input: CreateTokenInput!) {
        createToken(input: $input) {
            payload {
                id
            }
        }
    }
""")

create_permanent = gql("""
    mutation createPermanentToken($input: CreatePermanentTokenInput!) {
        createPermanentToken(input: $input) {
            payload {
                id
            }
        }
    }
""")
load_facts = gql("""
query getDomains {
    domains {
        id
        title
        facts {
            activeVisitors
            viewsToday
            viewsMonth
            viewsYear
        }
    }
}
""")
load_stats = gql("""
query getDomains {
    domains {
        title
        statistics {
            views(interval: DAILY, type: UNIQUE, limit: 9999) {
                # id
                count
                value
            }
        }
    }
}
""")

load_pages = gql("""
query getDomains {
    domains {
    title
    statistics {
        pages(sorting: TOP) {
                # id
                count
                # created
                value
            }
        }
    }
}
""")
schema_str = open(path.dirname(__file__) + '/ackee.graphql').read()
token = environ.get("ACKEE_TOKEN", "")


def create_client(headers=None, schema=None):
    return Client(
        schema=schema,
        transport=AIOHTTPTransport(
            url="https://ackee.discours.io/api",
            ssl=create_default_context(),
            headers=headers
        )
    )


class ViewedStorage:
    lock = asyncio.Lock()
    by_shouts = {}
    by_topics = {}
    views = None
    domains = None
    period = 24 * 60 * 60  # one time a day
    client = None
    auth_result = None

    @staticmethod
    async def init():
        if token:
            self = ViewedStorage
            async with self.lock:
                self.client = create_client({
                    "Authorization": "Bearer %s" % str(token)
                }, schema=schema_str)
                print("[stat.viewed] authorized permanentely by ackee.discours.io: %s" % token)
        else:
            print("[stat.viewed] please, set ACKEE_TOKEN")

    @staticmethod
    async def update(session):
        self = ViewedStorage
        async with self.lock:
            try:
                self.views = await self.client.execute_async(load_stats)
                print("[stat.viewed] ackee views updated")
                print(self.views)
            except Exception as e:
                raise e

    @staticmethod
    async def update_pages(session):
        self = ViewedStorage
        async with self.lock:
            try:
                self.pages = await self.client.execute_async(load_pages)
                self.pages = self.pages["domains"][0]["statistics"]["pages"]
                print("[stat.viewed] ackee pages updated")
                # print(self.pages)
                shouts = {}
                try:
                    for page in self.pages:
                        p = page["value"].split("?")[0]
                        # print(p)
                        slug = p.split('https://new.discours.io/')[-1]
                        shouts[slug] = page["count"]
                    # print(shouts)
                    for slug, v in shouts:
                        await ViewedStorage.increment(slug, v)
                except Exception:
                    pass
                print("[stat.viewed] %d pages collected " % len(shouts.keys()))
            except Exception as e:
                raise e

    @staticmethod
    async def get_facts():
        self = ViewedStorage
        async with self.lock:
            return self.client.execute_async(load_facts)

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
        failed = 0
        while True:
            try:
                with local_session() as session:
                    # await self.update(session)
                    await self.update_pages(session)
                    failed = 0
            except Exception:
                failed += 1
                print("[stat.viewed] update failed #%d, wait 10 seconds" % failed)
                if failed > 3:
                    print("[stat.viewed] not trying to update anymore")
                    break
            if failed == 0:
                when = datetime.now(timezone.utc) + timedelta(seconds=self.period)
                t = format(when.astimezone().isoformat())
                t = t.split("T")[0] + " " + t.split("T")[1].split(".")[0]
                print("[stat.viewed] next update: %s" % t)
                await asyncio.sleep(self.period)
            else:
                await asyncio.sleep(10)
                print("[stat.viewed] trying to update data again...")
