
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import selectinload
from orm.base import local_session
from orm.reaction import Reaction
from orm.shout import Shout
from storages.reactions import ReactionsStorage
from storages.viewed import ViewedByDay


class ShoutsCache:
	limit = 200
	period = 60*60 #1 hour
	lock = asyncio.Lock()

	@staticmethod
	async def prepare_recent_published():
		with local_session() as session:
			stmt = select(Shout).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				where(Shout.publishedAt != None).\
				order_by(desc("publishedAt")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ReactionsStorage.shout_rating(shout.slug) or 0
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.recent_published = shouts
			print("[storage.shoutscache] %d recently published shouts " % len(shouts))

	@staticmethod
	async def prepare_recent_all():
		with local_session() as session:
			stmt = select(Shout).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				order_by(desc("createdAt")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ReactionsStorage.shout_rating(shout.slug) or 0
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.recent_all = shouts
			print("[storage.shoutscache] %d recently created shouts " % len(shouts))

	@staticmethod
	async def prepare_recent_reacted():
		with local_session() as session:
			stmt = select(Shout, func.max(Reaction.createdAt).label("reactionCreatedAt")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(Reaction).\
				where(and_(Shout.publishedAt != None, Reaction.deletedAt == None)).\
				group_by(Shout.slug).\
				order_by(desc("reactionCreatedAt")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ReactionsStorage.shout_rating(shout.slug) or 0
				shouts.append(shout)
			async with ShoutsCache.lock:
				ShoutsCache.recent_reacted = shouts
				print("[storage.shoutscache] %d recently reacted shouts " % len(shouts))


	@staticmethod
	async def prepare_top_overall():
		with local_session() as session:
			# with reacted times counter
			stmt = select(Shout, 
				func.count(Reaction.id).label("reacted")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics), selectinload(Shout.reactions)).\
				join(Reaction).\
				where(and_(Shout.publishedAt != None, Reaction.deletedAt == None)).\
				group_by(Shout.slug).\
				order_by(desc("reacted")).\
				limit(ShoutsCache.limit)
			shouts = []
			# with rating synthetic counter
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ReactionsStorage.shout_rating(shout.slug) or 0
				shouts.append(shout)
			shouts.sort(key = lambda shout: shout.rating, reverse = True)
			async with ShoutsCache.lock:
				print("[storage.shoutscache] %d top shouts " % len(shouts))
				ShoutsCache.top_overall = shouts

	@staticmethod
	async def prepare_top_month():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			stmt = select(Shout, func.count(Reaction.id).label("reacted")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(Reaction).\
				where(and_(Shout.createdAt > month_ago, Shout.publishedAt != None)).\
				group_by(Shout.slug).\
				order_by(desc("reacted")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ReactionsStorage.shout_rating(shout.slug) or 0
				shouts.append(shout)
			shouts.sort(key = lambda shout: shout.rating, reverse = True)
			async with ShoutsCache.lock:
				print("[storage.shoutscache] %d top month shouts " % len(shouts))
				ShoutsCache.top_month = shouts

	@staticmethod
	async def prepare_top_viewed():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			stmt = select(Shout, func.sum(ViewedByDay.value).label("viewed")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(ViewedByDay).\
				where(and_(ViewedByDay.day > month_ago, Shout.publishedAt != None)).\
				group_by(Shout.slug).\
				order_by(desc("viewed")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ReactionsStorage.shout_rating(shout.slug) or 0
				shouts.append(shout)
		# shouts.sort(key = lambda shout: shout.viewed, reverse = True)
		async with ShoutsCache.lock:
			print("[storage.shoutscache] %d top viewed shouts " % len(shouts))
			ShoutsCache.top_viewed = shouts

	@staticmethod
	async def worker():
		while True:
			try:
				await ShoutsCache.prepare_top_month()
				await ShoutsCache.prepare_top_overall()
				await ShoutsCache.prepare_top_viewed()
				await ShoutsCache.prepare_recent_published()
				await ShoutsCache.prepare_recent_all()
				await ShoutsCache.prepare_recent_reacted()
				print("[storage.shoutscache] updated")
			except Exception as err:
				print("[storage.shoutscache] error: %s" % (err))
				raise err
			await asyncio.sleep(ShoutsCache.period)
