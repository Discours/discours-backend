import asyncio
from base.orm import local_session
from orm.reaction import ReactionKind, Reaction
from services.zine.topics import TopicStorage
from services.stat.viewed import ViewedStorage


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
    reacted = {"shouts": {}, "topics": {}, "reactions": {}, "authors": {}}
    rating = {"shouts": {}, "topics": {}, "reactions": {}}
    reactions = []
    to_flush = []
    period = 30 * 60  # sec
    lock = asyncio.Lock()
    modified_shouts = set([])

    @staticmethod
    async def get_shout_stat(slug):
        return {
            "viewed": await ViewedStorage.get_shout(slug),
            "reacted": len(await ReactedStorage.get_shout(slug)),
            "commented": len(await ReactedStorage.get_comments(slug)),
            "rating": await ReactedStorage.get_rating(slug),
        }

    @staticmethod
    async def get_shout(shout_slug):
        self = ReactedStorage
        async with self.lock:
            return self.reacted["shouts"].get(shout_slug, [])

    @staticmethod
    async def get_author(user_slug):
        self = ReactedStorage
        async with self.lock:
            return self.reacted["authors"].get(user_slug, [])

    @staticmethod
    async def get_shouts_by_author(user_slug):
        self = ReactedStorage
        async with self.lock:
            author_reactions = self.reacted["authors"].get(user_slug, [])
            shouts = []
            for r in author_reactions:
                if r.shout not in shouts:
                    shouts.append(r.shout)
            return shouts

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
            # renew reactions by shout
            self.reacted["shouts"][r.shout] = self.reacted["shouts"].get(r.shout, [])
            self.reacted["shouts"][r.shout].append(r)
            # renew reactions by author
            self.reacted["authors"][r.createdBy] = self.reacted["authors"].get(r.createdBy, [])
            self.reacted["authors"][r.createdBy].append(r)
            # renew reactions by topic
            shout_topics = await TopicStorage.get_topics_by_slugs([r.shout, ])
            for t in shout_topics:
                self.reacted["topics"][t] = self.reacted["topics"].get(t, [])
                self.reacted["topics"][t].append(r)
                self.rating["topics"][t] = \
                    self.rating["topics"].get(t, 0) + kind_to_rate(r.kind)
            if r.replyTo:
                # renew reactions replies
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
        self.modified_shouts = list(set([r.shout for r in all_reactions]))
        print("[stat.reacted] %d shouts with reactions" % len(self.modified_shouts))

    @staticmethod
    async def recount_changed(session):
        self = ReactedStorage
        async with self.lock:
            sss = list(self.modified_shouts)
            c = 0
            for slug in sss:
                siblings = session.query(Reaction).where(Reaction.shout == slug).all()
                c += len(siblings)
                await self.recount(siblings)

            print("[stat.reacted] %d reactions recounted" % c)
            print("[stat.reacted] %d shouts" % len(self.modified_shouts))
            print("[stat.reacted] %d topics" % len(self.reacted["topics"].values()))
            print("[stat.reacted] %d authors" % len(self.reacted["authors"].values()))
            print("[stat.reacted] %d replies" % len(self.reacted["reactions"]))
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
