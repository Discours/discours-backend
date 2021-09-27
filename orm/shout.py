from typing import List
from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from orm import Permission, User, Topic
from orm.comment import Comment
from orm.base import Base

from functools import reduce

class ShoutAuthor(Base):
	__tablename__ = "shout_author"
	
	id = None
	shout = Column(ForeignKey('shout.id'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)
	
class ShoutViewer(Base):
	__tablename__ = "shout_viewer"
	
	id = None
	shout = Column(ForeignKey('shout.id'), primary_key = True)
	user = Column(ForeignKey('user.id'), primary_key = True)

class ShoutTopic(Base):
	__tablename__ = 'shout_topic'
	
	id = None
	shout = Column(ForeignKey('shout.id'), primary_key = True)
	topic = Column(ForeignKey('topic.id'), primary_key = True)

class ShoutRating(Base):
	__tablename__ = "shout_rating"

	id = None
	rater_id = Column(ForeignKey('user.id'), primary_key = True)
	shout_id = Column(ForeignKey('shout.id'), primary_key = True)
	ts = Column(DateTime, nullable=False, default = datetime.now, comment="Timestamp")
	value = Column(Integer)

class ShoutRatingStorage:

	def __init__(self, session):
		self.ratings = session.query(ShoutRating).all()

	def get_rating(self, shout_id):
		shout_ratings = list(filter(lambda x: x.shout_id == shout_id, self.ratings))
		return reduce((lambda x, y: x + y.value), shout_ratings, 0)

	def update_rating(self, new_rating):
		rating = next((x for x in self.ratings \
			if x.rater_id == new_rating.rater_id and x.shout_id == new_rating.shout_id), None)
		if rating:
			rating.value = new_rating.value
			rating.ts = new_rating.ts
		else:
			self.ratings.append(new_rating)


class ShoutViewByDay(Base):
	__tablename__ = "shout_view_by_day"

	id = None
	shout_id = Column(ForeignKey('shout.id'), primary_key = True)
	day = Column(DateTime, primary_key = True, default = datetime.now)
	value = Column(Integer)

class ShoutViewStorage:

	def __init__(self, session):
		self.views = session.query(ShoutViewByDay).all()
		self.this_day_views = {}
		for view in self.views:
			shout_id = view.shout_id
			if not shout_id in self.this_day_views:
				self.this_day_views[shout_id] = view
			this_day_view = self.this_day_views[shout_id]
			if this_day_view.day < view.day:
				self.this_day_views[shout_id] = view

	def get_view(self, shout_id):
		shout_views = list(filter(lambda x: x.shout_id == shout_id, self.views))
		return reduce((lambda x, y: x + y.value), shout_views, 0)

	def inc_view(self, shout_id):
		this_day_view = self.this_day_views.get(shout_id)
		if not this_day_view:
			this_day_view = ShoutViewByDay.create(shout_id = shout_id, value = 1)
			self.this_day_views[shout_id] = this_day_view
			self.views.append(this_day_view)
		else:
			this_day_view.value = this_day_view.value + 1
			this_day_view.modified = True

	def flush_changes(self, session):
		for view in self.this_day_views.values():
			if getattr(view, "modified", False):
				session.add(view)
				flag_modified(view, "value")
				view.modified = False
		session.commit()


class Shout(Base):
	__tablename__ = 'shout'

	# NOTE: automatic ID here

	slug: str = Column(String, nullable=False, unique=True)
	community: int = Column(Integer, ForeignKey("community.id"), nullable=True, comment="Community")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")
	replyTo: int = Column(ForeignKey("shout.id"), nullable=True)
	versionOf: int = Column(ForeignKey("shout.id"), nullable=True)
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
	old_id: str = Column(String, nullable = True)
