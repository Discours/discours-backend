from typing import List
from datetime import datetime, timedelta
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from orm import Permission, User, Topic
from orm.comment import Comment
from orm.base import Base, local_session

from functools import reduce

import asyncio

class ShoutAuthor(Base):
	__tablename__ = "shout_author"
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)
	
class ShoutViewer(Base):
	__tablename__ = "shout_viewer"
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)

class ShoutTopic(Base):
	__tablename__ = 'shout_topic'
	
	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	topic = Column(ForeignKey('topic.slug'), primary_key = True)

class ShoutRating(Base):
	__tablename__ = "shout_rating"

	id = None
	rater = Column(ForeignKey('user.id'), primary_key = True)
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	ts = Column(DateTime, nullable=False, default = datetime.now, comment="Timestamp")
	value = Column(Integer)

class ShoutRatingStorage:

	ratings = []

	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		ShoutRatingStorage.ratings = session.query(ShoutRating).all()

	@staticmethod
	async def get_rating(shout_slug):
		async with ShoutRatingStorage.lock:
			shout_ratings = list(filter(lambda x: x.shout == shout_slug, ShoutRatingStorage.ratings))
		return reduce((lambda x, y: x + y.value), shout_ratings, 0)

	@staticmethod
	async def update_rating(new_rating):
		async with ShoutRatingStorage.lock:
			rating = next((x for x in ShoutRatingStorage.ratings \
				if x.rater == new_rating.rater and x.shout == new_rating.shout), None)
			if rating:
				rating.value = new_rating.value
				rating.ts = new_rating.ts
			else:
				ShoutRatingStorage.ratings.append(new_rating)


class ShoutViewByDay(Base):
	__tablename__ = "shout_view_by_day"

	id = None
	shout = Column(ForeignKey('shout.slug'), primary_key = True)
	day = Column(DateTime, primary_key = True, default = datetime.now)
	value = Column(Integer)

class ShoutViewStorage:

	views = []
	this_day_views = {}

	period = 30*60 #sec

	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = ShoutViewStorage
		self.views = session.query(ShoutViewByDay).all()
		for view in self.views:
			shout_slug = view.shout
			if not shout_slug in self.this_day_views:
				self.this_day_views[shout_slug] = view
			this_day_view = self.this_day_views[shout_slug]
			if this_day_view.day < view.day:
				self.this_day_views[shout_slug] = view

	@staticmethod
	async def get_view(shout_slug):
		async with ShoutViewStorage.lock:
			shout_views = list(filter(lambda x: x.shout == shout_slug, ShoutViewStorage.views))
		return reduce((lambda x, y: x + y.value), shout_views, 0)

	@staticmethod
	async def inc_view(shout_slug):
		self = ShoutViewStorage
		async with ShoutViewStorage.lock:
			this_day_view = self.this_day_views.get(shout_slug)
			day_start = datetime.now().replace(hour = 0, minute = 0, second = 0)
			if not this_day_view or this_day_view.day < day_start:
				this_day_view = ShoutViewByDay.create(shout = shout_slug, value = 1)
				self.this_day_views[shout_slug] = this_day_view
				self.views.append(this_day_view)
			else:
				this_day_view.value = this_day_view.value + 1
				this_day_view.modified = True

	@staticmethod
	async def flush_changes(session):
		async with ShoutViewStorage.lock:
			for view in ShoutViewStorage.this_day_views.values():
				if getattr(view, "modified", False):
					session.add(view)
					flag_modified(view, "value")
					view.modified = False
		session.commit()

	@staticmethod
	async def worker():
		print("ShoutViewStorage worker start")
		while True:
			try:
				print("ShoutViewStorage worker: flush changes")
				with local_session() as session:
					await ShoutViewStorage.flush_changes(session)
			except Exception as err:
				print("ShoutViewStorage worker: error = %s" % (err))
			await asyncio.sleep(ShoutViewStorage.period)


class Shout(Base):
	__tablename__ = 'shout'

	id = None

	slug: str = Column(String, primary_key=True)
	community: int = Column(Integer, ForeignKey("community.id"), nullable=True, comment="Community")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	replyTo: int = Column(ForeignKey("shout.slug"), nullable=True)
	versionOf: int = Column(ForeignKey("shout.slug"), nullable=True)
	tags: str = Column(String, nullable=True)
	publishedBy: bool = Column(ForeignKey("user.id"), nullable=True)
	publishedAt: str = Column(DateTime, nullable=True)
	cover: str = Column(String, nullable = True)
	title: str = Column(String, nullable = True)
	subtitle: str = Column(String, nullable = True)
	comments = relationship(Comment)
	layout: str = Column(String, nullable = True)
	authors = relationship(lambda: User, secondary=ShoutAuthor.__tablename__) # NOTE: multiple authors
	topics = relationship(lambda: Topic, secondary=ShoutTopic.__tablename__)
	visibleFor = relationship(lambda: User, secondary=ShoutViewer.__tablename__)
