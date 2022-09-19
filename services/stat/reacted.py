import asyncio
from base.orm import local_session
from orm.reaction import ReactionKind, Reaction
from services.zine.topics import TopicStorage


def kind_to_rate(kind) -> int:
    if kind in [
        ReactionKind.AGREE,
        ReactionKind.LIKE,
        ReactionKind.PROOF,
        ReactionKind.ACCEPT,
    ]:
        return 1
    elif kind in [
        ReactionKind.DISAGREE,
        ReactionKind.DISLIKE,
        ReactionKind.DISPROOF,
        ReactionKind.REJECT,
    ]:
        return -1
    else:
        return 0


class ReactedStorage:
    reacted = {"shouts": {}, "topics": {}, "reactions": {}}
    rating = {"shouts": {}, "topics": {}, "reactions": {}}
    reactions = []
    to_flush = []
    period = 30 * 60  # sec
    lock = asyncio.Lock()
    modified_shouts = set([])

    @staticmethod
    async def get_shout(shout_slug):
        self = ReactedStorage
        async with self.lock:
            return self.reacted["shouts"].get(shout_slug, [])

    @staticmethod
    async def get_topic(topic_slug):
        self = ReactedStorage
        async with self.lock:
            return self.reacted["topics"].get(topic_slug, [])

    @staticmethod
    async def get_comments(shout_slug):
        self = ReactedStorage
        async with self.lock:
            return list(
                filter(lambda r: bool(r.body), self.reacted["shouts"].get(shout_slug, {}))
            )

    @staticmethod
    async def get_topic_comments(topic_slug):
        self = ReactedStorage
        async with self.lock:
            return list(
                filter(lambda r: bool(r.body), self.reacted["topics"].get(topic_slug, []))
            )

    @staticmethod
    async def get_reaction_comments(reaction_id):
        self = ReactedStorage
        async with self.lock:
            return list(
                filter(
                    lambda r: bool(r.body), self.reacted["reactions"].get(reaction_id, {})
                )
            )

    @staticmethod
    async def get_reaction(reaction_id):
        self = ReactedStorage
        async with self.lock:
            return self.reacted["reactions"].get(reaction_id, [])

    @staticmethod
    async def get_rating(shout_slug):
        self = ReactedStorage
        rating = 0
        async with self.lock:
            for r in self.reacted["shouts"].get(shout_slug, []):
                rating = rating + kind_to_rate(r.kind)
        return rating

    @staticmethod
    async def get_topic_rating(topic_slug):
        self = ReactedStorage
        rating = 0
        async with self.lock:
            for r in self.reacted["topics"].get(topic_slug, []):
                rating = rating + kind_to_rate(r.kind)
        return rating

    @staticmethod
    async def get_reaction_rating(reaction_id):
        self = ReactedStorage
        rating = 0
        async with self.lock:
            for r in self.reacted["reactions"].get(reaction_id, []):
                rating = rating + kind_to_rate(r.kind)
        return rating

    @staticmethod
    async def react(reaction):
        ReactedStorage.modified_shouts.add(reaction.shout)

    @staticmethod
    async def recount(reactions):
        self = ReactedStorage
        for r in reactions:
            # renew shout counters
            self.reacted["shouts"][r.shout] = self.reacted["shouts"].get(r.shout, [])
            self.reacted["shouts"][r.shout].append(r)
            # renew topics counters
            shout_topics = await TopicStorage.get_topics_by_slugs([r.shout, ])
            for t in shout_topics:
                self.reacted["topics"][t] = self.reacted["topics"].get(t, [])
                self.reacted["topics"][t].append(r)
                self.rating["topics"][t] = \
                    self.rating["topics"].get(t, 0) + kind_to_rate(r.kind)
            if r.replyTo:
                # renew reaction counters
                self.reacted["reactions"][r.replyTo] = \
                    self.reacted["reactions"].get(r.replyTo, [])
                self.reacted["reactions"][r.replyTo].append(r)
                self.rating["reactions"][r.replyTo] = \
                    self.rating["reactions"].get(r.replyTo, 0) + kind_to_rate(r.kind)
            else:
                # renew shout rating
                self.rating["shouts"][r.shout] = \
                    self.rating["shouts"].get(r.shout, 0) + kind_to_rate(r.kind)

    @staticmethod
    def init(session):
        self = ReactedStorage
        all_reactions = session.query(Reaction).all()
        self.modified_shouts = set([r.shout for r in all_reactions])
        print("[stat.reacted] %d shouts with reactions updates" % len(self.modified_shouts))

    @staticmethod
    async def recount_changed(session):
        self = ReactedStorage
        async with self.lock:
            print('[stat.reacted] recounting...')
            for slug in list(self.modified_shouts):
                siblings = session.query(Reaction).where(Reaction.shout == slug).all()
                await self.recount(siblings)

            print("[stat.reacted] %d shouts with reactions updates" % len(self.modified_shouts))
            print("[stat.reacted] %d topics reacted" % len(self.reacted["topics"].values()))
            print("[stat.reacted] %d shouts reacted" % len(self.reacted["shouts"]))
            print("[stat.reacted] %d reactions reacted" % len(self.reacted["reactions"]))
            self.modified_shouts = set([])

    @staticmethod
    async def worker():
        while True:
            try:
                with local_session() as session:
                    await ReactedStorage.recount_changed(session)
            except Exception as err:
                print("[stat.reacted] recount error %s" % (err))
            await asyncio.sleep(ReactedStorage.period)
