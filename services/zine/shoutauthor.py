import asyncio
import time
from base.orm import local_session
from orm.shout import ShoutAuthor


class ShoutAuthorStorage:
    authors_by_shout = {}
    lock = asyncio.Lock()
    # period = 30 * 60  # sec

    @staticmethod
    async def load_captions(session):
        self = ShoutAuthorStorage
        sas = session.query(ShoutAuthor).all()
        for sa in sas:
            self.authors_by_shout[sa.shout] = self.authors_by_shout.get(sa.shout, {})
            self.authors_by_shout[sa.shout][sa.user] = sa.caption
        print("[zine.authors] %d shouts indexed by authors" % len(self.authors_by_shout))

    @staticmethod
    async def get_author_caption(shout, author):
        self = ShoutAuthorStorage
        async with self.lock:
            return self.authors_by_shout.get(shout, {}).get(author)

    @staticmethod
    async def set_author_caption(shout, author, caption):
        self = ShoutAuthorStorage
        async with self.lock:
            self.authors_by_shout[shout] = self.authors_by_shout.get(shout, {})
            self.authors_by_shout[shout][author] = caption
            return {
                "error": None,
            }

    @staticmethod
    async def worker():
        self = ShoutAuthorStorage
        async with self.lock:
            # while True:
            try:
                with local_session() as session:
                    ts = time.time()
                    await self.load_captions(session)
                    print("[zine.authors] load_captions took %fs " % (time.time() - ts))
            except Exception as err:
                print("[zine.authors] error indexing by author: %s" % (err))
            # await asyncio.sleep(self.period)
