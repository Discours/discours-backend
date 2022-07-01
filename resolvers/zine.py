from orm import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay, \
    User, Community, Resource, ShoutRatingStorage, ShoutViewStorage, \
        Comment, CommentRating, Topic, ShoutCommentsSubscription
from orm.community import CommunitySubscription
from orm.base import local_session
from orm.user import UserStorage, AuthorSubscription
from orm.topic import TopicSubscription

from resolvers.base import mutation, query
from resolvers.comments import comments_subscribe, comments_unsubscribe
from auth.authenticate import login_required
from settings import SHOUTS_REPO

import subprocess
import asyncio
from datetime import datetime, timedelta

from pathlib import Path
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload


class GitTask:

	queue = asyncio.Queue()

	def __init__(self, input, username, user_email, comment):
		self.slug = input["slug"]
		self.shout_body = input["body"]
		self.username = username
		self.user_email = user_email
		self.comment = comment

		GitTask.queue.put_nowait(self)
	
	def init_repo(self):
		repo_path = "%s" % (SHOUTS_REPO)
		
		Path(repo_path).mkdir()
		
		cmd = "cd %s && git init && " \
			"git config user.name 'discours' && " \
			"git config user.email 'discours@discours.io' && " \
			"touch initial && git add initial && " \
			"git commit -m 'init repo'" \
			% (repo_path)
		output = subprocess.check_output(cmd, shell=True)
		print(output)

	def execute(self):
		repo_path = "%s" % (SHOUTS_REPO)
		
		if not Path(repo_path).exists():
			self.init_repo()

		#cmd = "cd %s && git checkout master" % (repo_path)
		#output = subprocess.check_output(cmd, shell=True)
		#print(output)

		shout_filename = "%s.mdx" % (self.slug)
		shout_full_filename = "%s/%s" % (repo_path, shout_filename)
		with open(shout_full_filename, mode='w', encoding='utf-8') as shout_file:
			shout_file.write(bytes(self.shout_body,'utf-8').decode('utf-8','ignore'))

		author = "%s <%s>" % (self.username, self.user_email)
		cmd = "cd %s && git add %s && git commit -m '%s' --author='%s'" % \
			(repo_path, shout_filename, self.comment, author)
		output = subprocess.check_output(cmd, shell=True)
		print(output)
	
	@staticmethod
	async def git_task_worker():
		print("[git.task] worker start")
		while True:
			task = await GitTask.queue.get()
			try:
				task.execute()
			except Exception as err:
				print("[git.task] worker error = %s" % (err))


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
				shout.ratings = await ShoutRatingStorage.get_ratings(shout.slug)
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.recent_published = shouts

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
				shout.ratings = await ShoutRatingStorage.get_ratings(shout.slug)
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.recent_all = shouts

	@staticmethod
	async def prepare_recent_commented():
		with local_session() as session:
			stmt = select(Shout, func.max(Comment.createdAt).label("commentCreatedAt")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(Comment).\
				where(and_(Shout.publishedAt != None, Comment.deletedAt == None)).\
				group_by(Shout.slug).\
				order_by(desc("commentCreatedAt")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.ratings = await ShoutRatingStorage.get_ratings(shout.slug)
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.recent_commented = shouts


	@staticmethod
	async def prepare_top_overall():
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutRating.value).label("rating")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(ShoutRating).\
				where(Shout.publishedAt != None).\
				group_by(Shout.slug).\
				order_by(desc("rating")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.ratings = await ShoutRatingStorage.get_ratings(shout.slug)
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.top_overall = shouts

	@staticmethod
	async def prepare_top_month():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutRating.value).label("rating")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(ShoutRating).\
				where(and_(Shout.createdAt > month_ago, Shout.publishedAt != None)).\
				group_by(Shout.slug).\
				order_by(desc("rating")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.ratings = await ShoutRatingStorage.get_ratings(shout.slug)
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.top_month = shouts

	@staticmethod
	async def prepare_top_viewed():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutViewByDay.value).label("views")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(ShoutViewByDay).\
				where(and_(ShoutViewByDay.day > month_ago, Shout.publishedAt != None)).\
				group_by(Shout.slug).\
				order_by(desc("views")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.ratings = await ShoutRatingStorage.get_ratings(shout.slug)
				shout.views = row.views
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.top_viewed = shouts

	@staticmethod
	async def worker():
		print("[shouts.cache] worker start")
		while True:
			try:
				print("[shouts.cache] updating...")
				await ShoutsCache.prepare_top_month()
				await ShoutsCache.prepare_top_overall()
				await ShoutsCache.prepare_top_viewed()
				await ShoutsCache.prepare_recent_published()
				await ShoutsCache.prepare_recent_all()
				await ShoutsCache.prepare_recent_commented()
				print("[shouts.cache] update finished")
			except Exception as err:
				print("[shouts.cache] worker error: %s" % (err))
			await asyncio.sleep(ShoutsCache.period)

@query.field("topViewed")
async def top_viewed(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.top_viewed[(page - 1) * size : page * size]

@query.field("topMonth")
async def top_month(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.top_month[(page - 1) * size : page * size]

@query.field("topOverall")
async def top_overall(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.top_overall[(page - 1) * size : page * size]

@query.field("recentPublished")
async def recent_published(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_published[(page - 1) * size : page * size]

@query.field("recentAll")
async def recent_all(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_all[(page - 1) * size : page * size]

@query.field("recentCommented")
async def recent_commented(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_commented[(page - 1) * size : page * size]

@mutation.field("viewShout")
async def view_shout(_, info, slug):
	await ShoutViewStorage.inc_view(slug)
	return {"error" : ""}

@query.field("getShoutBySlug")
async def get_shout_by_slug(_, info, slug):
	all_fields = [node.name.value for node in info.field_nodes[0].selection_set.selections]
	selected_fields = set(["authors", "topics"]).intersection(all_fields)
	select_options = [selectinload(getattr(Shout, field)) for field in selected_fields]

	with local_session() as session:
		shout = session.query(Shout).\
			options(select_options).\
			filter(Shout.slug == slug).first()

	if not shout:
		print(f"shout with slug {slug} not exist")
		return {} #TODO return error field

	shout.ratings = await ShoutRatingStorage.get_ratings(slug)
	return shout

@query.field("getShoutComments")
async def get_shout_comments(_, info, slug):
	with local_session() as session:
		comments = session.query(Comment).\
			options(selectinload(Comment.ratings)).\
			filter(Comment.shout == slug).\
			group_by(Comment.id).all()
	for comment in comments:
		comment.author = await UserStorage.get_user(comment.author)
	return comments

@query.field("shoutsByTopics")
async def shouts_by_topics(_, info, slugs, page, size):
	page = page - 1
	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutTopic).\
			where(and_(ShoutTopic.topic.in_(slugs), Shout.publishedAt != None)).\
			order_by(desc(Shout.publishedAt)).\
			limit(size).\
			offset(page * size)
	return shouts

@query.field("shoutsByAuthors")
async def shouts_by_authors(_, info, slugs, page, size):
	page = page - 1
	with local_session() as session:

		shouts = session.query(Shout).\
			join(ShoutAuthor).\
			where(and_(ShoutAuthor.user.in_(slugs), Shout.publishedAt != None)).\
			order_by(desc(Shout.publishedAt)).\
			limit(size).\
			offset(page * size)
	return shouts

@query.field("shoutsByCommunities")
async def shouts_by_communities(_, info, slugs, page, size):
	page = page - 1
	with local_session() as session:
		#TODO fix postgres high load
		shouts = session.query(Shout).distinct().\
			join(ShoutTopic).\
			where(and_(Shout.publishedAt != None,\
				ShoutTopic.topic.in_(\
				select(Topic.slug).where(Topic.community.in_(slugs))\
			))).\
			order_by(desc(Shout.publishedAt)).\
			limit(size).\
			offset(page * size)
	return shouts

@mutation.field("subscribe")
@login_required
async def subscribe(_, info, subscription, slug):
	user = info.context["request"].user

	try:
		if subscription == "AUTHOR":
			author_subscribe(user, slug)
		elif subscription == "TOPIC":
			topic_subscribe(user, slug)
		elif subscription == "COMMUNITY":
			community_subscribe(user, slug)
		elif comments_subscription == "COMMENTS":
			comments_subscribe(user, slug)
	except Exception as e:
		return {"error" : e}

	return {}

@mutation.field("unsubscribe")
@login_required
async def unsubscribe(_, info, subscription, slug):
	user = info.context["request"].user

	try:
		if subscription == "AUTHOR":
			author_unsubscribe(user, slug)
		elif subscription == "TOPIC":
			topic_unsubscribe(user, slug)
		elif subscription == "COMMUNITY":
			community_unsubscribe(user, slug)
		elif subscription == "COMMENTS":
			comments_unsubscribe(user, slug)
	except Exception as e:
		return {"error" : e}

	return {}


@mutation.field("rateShout")
@login_required
async def rate_shout(_, info, slug, value):
	auth = info.context["request"].auth
	user = info.context["request"].user

	with local_session() as session:
		rating = session.query(ShoutRating).\
			filter(and_(ShoutRating.rater == user.slug, ShoutRating.shout == slug)).first()
		if rating:
			rating.value = value;
			rating.ts = datetime.now()
			session.commit()
		else:
			rating = ShoutRating.create(
				rater = user.slug,
				shout = slug,
				value = value
			)

	await ShoutRatingStorage.update_rating(rating)

	return {"error" : ""}