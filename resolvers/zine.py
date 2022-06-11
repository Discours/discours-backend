from orm import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay, User, Community, Resource,\
	ShoutRatingStorage, ShoutViewStorage, Comment, CommentRating, Topic
from orm.base import local_session
from orm.user import UserStorage, AuthorSubscription
from orm.topic import TopicSubscription

from resolvers.base import mutation, query

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

		shout_filename = "%s.md" % (self.slug)
		shout_full_filename = "%s/%s" % (repo_path, shout_filename)
		with open(shout_full_filename, mode='w', encoding='utf-8') as shout_file:
			shout_file.write(self.shout_body)

		author = "%s <%s>" % (self.username, self.user_email)
		cmd = "cd %s && git add %s && git commit -m '%s' --author='%s'" % \
			(repo_path, shout_filename, self.comment, author)
		output = subprocess.check_output(cmd, shell=True)
		print(output)
	
	@staticmethod
	async def git_task_worker():
		print("git task worker start")
		while True:
			task = await GitTask.queue.get()
			try:
				task.execute()
			except Exception as err:
				print("git task worker error = %s" % (err))


class ShoutsCache:
	limit = 200
	period = 60*60 #1 hour
	lock = asyncio.Lock()

	@staticmethod
	async def prepare_recent_shouts():
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
			ShoutsCache.recent_shouts = shouts

	@staticmethod
	async def prepare_recent_all():
		with local_session() as session:
			stmt = select(Shout).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				where(Shout.publishedAt != None).\
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
		print("shouts cache worker start")
		while True:
			try:
				print("shouts cache updating...")
				await ShoutsCache.prepare_top_month()
				await ShoutsCache.prepare_top_overall()
				await ShoutsCache.prepare_top_viewed()
				await ShoutsCache.prepare_recent_shouts()
				await ShoutsCache.prepare_recent_all()
				await ShoutsCache.prepare_recent_commented()
				print("shouts cache update finished")
			except Exception as err:
				print("shouts cache worker error = %s" % (err))
			await asyncio.sleep(ShoutsCache.period)

class ShoutSubscriptions:
	lock = asyncio.Lock()
	subscriptions = []

	@staticmethod
	async def register_subscription(subs):
		async with ShoutSubscriptions.lock:
			ShoutSubscriptions.subscriptions.append(subs)
	
	@staticmethod
	async def del_subscription(subs):
		async with ShoutSubscriptions.lock:
			ShoutSubscriptions.subscriptions.remove(subs)
	
	@staticmethod
	async def send_shout(shout):
		async with ShoutSubscriptions.lock:
			for subs in ShoutSubscriptions.subscriptions:
				subs.put_nowait(shout)

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
async def recent_shouts(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_shouts[(page - 1) * size : page * size]

@query.field("recentAll")
async def recent_all(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_all[(page - 1) * size : page * size]

@query.field("recentCommented")
async def recent_commented(_, info, page, size):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_commented[(page - 1) * size : page * size]

@mutation.field("createShout")
@login_required
async def create_shout(_, info, input):
	user = info.context["request"].user

	topic_slugs = input.get("topic_slugs", [])
	if topic_slugs:
		del input["topic_slugs"]

	new_shout = Shout.create(**input)
	ShoutAuthor.create(
		shout = new_shout.slug,
		user = user.slug)
	
	if "mainTopic" in input:
		topic_slugs.append(input["mainTopic"])

	for slug in topic_slugs:
		topic = ShoutTopic.create(
			shout = new_shout.slug,
			topic = slug)
	new_shout.topic_slugs = topic_slugs

	task = GitTask(
		input,
		user.username,
		user.email,
		"new shout %s" % (new_shout.slug)
		)
		
	await ShoutSubscriptions.send_shout(new_shout)

	return {
		"shout" : new_shout
	}

@mutation.field("updateShout")
@login_required
async def update_shout(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id

	slug = input["slug"]

	session = local_session()
	user = session.query(User).filter(User.id == user_id).first()
	shout = session.query(Shout).filter(Shout.slug == slug).first()

	if not shout:
		return {
			"error" : "shout not found"
		}

	authors = [author.id for author in shout.authors]
	if not user_id in authors:
		scopes = auth.scopes
		print(scopes)
		if not Resource.shout_id in scopes:
			return {
				"error" : "access denied"
			}

	shout.update(input)
	shout.updatedAt = datetime.now()
	session.commit()
	session.close()

	for topic in input.get("topic_slugs", []):
		ShoutTopic.create(
			shout = slug,
			topic = topic)

	task = GitTask(
		input,
		user.username,
		user.email,
		"update shout %s" % (slug)
		)

	return {
		"shout" : shout
	}

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
		print("shout not exist")
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

@query.field("shoutsSubscribed")
@login_required
async def shouts_subscribed(_, info, page, size):
	user = info.context["request"].user
	with local_session() as session:
		shouts_by_topic = session.query(Shout).\
			join(ShoutTopic).\
			join(TopicSubscription, ShoutTopic.topic == TopicSubscription.topic).\
			where(and_(Shout.publishedAt != None, TopicSubscription.subscriber == user.slug))
		shouts_by_author = session.query(Shout).\
			join(ShoutAuthor).\
			join(AuthorSubscription, ShoutAuthor.user == AuthorSubscription.author).\
			where(and_(Shout.publishedAt != None, AuthorSubscription.subscriber == user.slug))
		shouts = shouts_by_topic.union(shouts_by_author).\
			order_by(desc(Shout.publishedAt)).\
			limit(size).\
			offset( (page - 1) * size)

	return shouts

@query.field("shoutsReviewed")
@login_required
async def shouts_reviewed(_, info, page, size):
	user = info.context["request"].user
	with local_session() as session:
		shouts_by_rating = session.query(Shout).\
			join(ShoutRating).\
			where(and_(Shout.publishedAt != None, ShoutRating.rater == user.slug))
		shouts_by_comment = session.query(Shout).\
			join(Comment).\
			where(and_(Shout.publishedAt != None, Comment.author == user.id))
		shouts = shouts_by_rating.union(shouts_by_comment).\
			order_by(desc(Shout.publishedAt)).\
			limit(size).\
			offset( (page - 1) * size)

	return shouts

@query.field("shoutsCandidates")
@login_required
async def shouts_candidates(_, info, size):
	user = info.context["request"].user
	#TODO: postgres heavy load
	with local_session() as session:
		shouts = session.query(Shout).distinct().\
			outerjoin(ShoutRating).\
			where(and_(Shout.publishedAt != None, ShoutRating.rater != user.slug)).\
			order_by(desc(Shout.publishedAt)).\
			limit(size)

	return shouts

@query.field("shoutsCommentedByUser")
async def shouts_commented_by_user(_, info, slug, page, size):
	user = await UserStorage.get_user_by_slug(slug)
	if not user:
		return {}

	with local_session() as session:
		shouts = session.query(Shout).\
			join(Comment).\
			where(Comment.author == user.id).\
			order_by(desc(Comment.createdAt)).\
			limit(size).\
			offset( (page - 1) * size)
	return shouts

@query.field("shoutsRatedByUser")
@login_required
async def shouts_rated_by_user(_, info, page, size):
	user = info.context["request"].user

	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutRating).\
			where(ShoutRating.rater == user.slug).\
			order_by(desc(ShoutRating.ts)).\
			limit(size).\
			offset( (page - 1) * size)

	return {
		"shouts" : shouts
	}

@query.field("userUnpublishedShouts")
@login_required
async def user_unpublished_shouts(_, info, page, size):
	user = info.context["request"].user

	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutAuthor).\
			where(and_(Shout.publishedAt == None, ShoutAuthor.user == user.slug)).\
			order_by(desc(Shout.createdAt)).\
			limit(size).\
			offset( (page - 1) * size)

	return {
		"shouts" : shouts
	}
