import asyncio
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm.attributes import flag_modified
from base.orm import Base, local_session
from orm.topic import ShoutTopic


class ViewedByDay(Base):
    __tablename__ = "viewed_by_day"

    id = None
    shout = Column(ForeignKey("shout.slug"), primary_key=True)
    day = Column(DateTime, primary_key=True, default=datetime.now)
    value = Column(Integer)


class ViewedStorage:
    viewed = {"shouts": {}, "topics": {}, "reactions": {}}
    this_day_views = {}
    to_flush = []
    period = 30 * 60  # sec
    lock = asyncio.Lock()

    @staticmethod
    def init(session):
        self = ViewedStorage
        views = session.query(ViewedByDay).all()

        for view in views:
            shout = view.shout
            topics = (
                session.query(ShoutTopic.topic).filter(ShoutTopic.shout == shout).all()
            )
            value = view.value
            if shout:
                old_value = self.viewed["shouts"].get(shout, 0)
                self.viewed["shouts"][shout] = old_value + value
            for t in topics:
                old_topic_value = self.viewed["topics"].get(t, 0)
                self.viewed["topics"][t] = old_topic_value + value
            if shout not in self.this_day_views:
                self.this_day_views[shout] = view
            this_day_view = self.this_day_views[shout]
            if this_day_view.day < view.day:
                self.this_day_views[shout] = view

        print("[stat.viewed] %d shouts viewed" % len(views))

    @staticmethod
    async def get_shout(shout_slug):
        self = ViewedStorage
        async with self.lock:
            return self.viewed["shouts"].get(shout_slug, 0)

    @staticmethod
    async def get_topic(topic_slug):
        self = ViewedStorage
        async with self.lock:
            return self.viewed["topics"].get(topic_slug, 0)

    @staticmethod
    async def get_reaction(reaction_id):
        self = ViewedStorage
        async with self.lock:
            return self.viewed["reactions"].get(reaction_id, 0)

    @staticmethod
    async def increment(shout_slug):
        self = ViewedStorage
        async with self.lock:
            this_day_view = self.this_day_views.get(shout_slug)
            day_start = datetime.now().replace(hour=0, minute=0, second=0)
            if not this_day_view or this_day_view.day < day_start:
                if this_day_view and getattr(this_day_view, "modified", False):
                    self.to_flush.append(this_day_view)
                this_day_view = ViewedByDay.create(shout=shout_slug, value=1)
                self.this_day_views[shout_slug] = this_day_view
            else:
                this_day_view.value = this_day_view.value + 1
            this_day_view.modified = True
            self.viewed["shouts"][shout_slug] = (
                self.viewed["shouts"].get(shout_slug, 0) + 1
            )
            with local_session() as session:
                topics = (
                    session.query(ShoutTopic.topic)
                    .where(ShoutTopic.shout == shout_slug)
                    .all()
                )
                for t in topics:
                    self.viewed["topics"][t] = self.viewed["topics"].get(t, 0) + 1
            flag_modified(this_day_view, "value")

    @staticmethod
    async def flush_changes(session):
        self = ViewedStorage
        async with self.lock:
            for view in self.this_day_views.values():
                if getattr(view, "modified", False):
                    session.add(view)
                    flag_modified(view, "value")
                    view.modified = False
            for view in self.to_flush:
                session.add(view)
            self.to_flush.clear()
        session.commit()

    @staticmethod
    async def worker():
        while True:
            try:
                with local_session() as session:
                    await ViewedStorage.flush_changes(session)
                    print("[stat.viewed] periodical flush")
            except Exception as err:
                print("[stat.viewed] errror: %s" % (err))
            await asyncio.sleep(ViewedStorage.period)
