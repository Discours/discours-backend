from orm import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay, User, Community, Resource,\
	ShoutRatingStorage, ShoutViewStorage
from orm.base import local_session

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
		
		cmd = "cd %s && git init && touch initial && git add initial && git commit -m 'init repo'" % (repo_path)
		output = subprocess.check_output(cmd, shell=True)
		print(output)

	def execute(self):
		repo_path = "%s" % (SHOUTS_REPO)
		
		if not Path(repo_path).exists():
			self.init_repo()

		cmd = "cd %s && git checkout master" % (repo_path)
		output = subprocess.check_output(cmd, shell=True)
		print(output)

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
	limit = 50
	period = 60*60 #1 hour
	lock = asyncio.Lock()

	@staticmethod
	async def prepare_recent_shouts():
		with local_session() as session:
			stmt = select(Shout).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				order_by(desc("createdAt")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ShoutRatingStorage.get_rating(shout.id)
				shout.views = await ShoutViewStorage.get_view(shout.id)
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.recent_shouts = shouts


	@staticmethod
	async def prepare_top_overall():
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutRating.value).label("rating")).\
				options(selectinload(Shout.authors), selectinload(Shout.topics)).\
				join(ShoutRating).\
				group_by(Shout.id).\
				order_by(desc("rating")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = row.rating
				shout.views = await ShoutViewStorage.get_view(shout.id)
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
				where(Shout.createdAt > month_ago).\
				group_by(Shout.id).\
				order_by(desc("rating")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = row.rating
				shout.views = await ShoutViewStorage.get_view(shout.id)
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
				where(ShoutViewByDay.day > month_ago).\
				group_by(Shout.id).\
				order_by(desc("views")).\
				limit(ShoutsCache.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = await ShoutRatingStorage.get_rating(shout.id)
				shout.views = row.views
				shouts.append(shout)
		async with ShoutsCache.lock:
			ShoutsCache.top_viewed = shouts

	@staticmethod
	async def prepare_top_authors():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			shout_with_view = select(Shout.id, func.sum(ShoutViewByDay.value).label("view")).\
				join(ShoutViewByDay).\
				where(ShoutViewByDay.day > month_ago).\
				group_by(Shout.id).\
				order_by(desc("view")).cte()
			stmt = select(ShoutAuthor.user, func.sum(shout_with_view.c.view).label("view")).\
				join(shout_with_view, ShoutAuthor.shout == shout_with_view.c.id).\
				group_by(ShoutAuthor.user).\
				order_by(desc("view")).\
				limit(ShoutsCache.limit)
			authors = {}
			for row in session.execute(stmt):
				authors[row.user] = row.view
			authors_ids = authors.keys()
			authors = session.query(User).filter(User.id.in_(authors_ids)).all()
		async with ShoutsCache.lock:
			ShoutsCache.top_authors = authors


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
				await ShoutsCache.prepare_top_authors()
				print("shouts cache update finished")
			except Exception as err:
				print("shouts cache worker error = %s" % (err))
			await asyncio.sleep(ShoutsCache.period)


@query.field("topViewed")
async def top_viewed(_, info, limit):
	async with ShoutsCache.lock:
		return ShoutsCache.top_viewed[:limit]

@query.field("topMonth")
async def top_month(_, info, limit):
	async with ShoutsCache.lock:
		return ShoutsCache.top_month[:limit]

@query.field("topOverall")
async def top_overall(_, info, limit):
	async with ShoutsCache.lock:
		return ShoutsCache.top_overall[:limit]

@query.field("recents")
async def recent_shouts(_, info, limit):
	async with ShoutsCache.lock:
		return ShoutsCache.recent_shouts[:limit]


@query.field("topAuthors")
async def top_authors(_, info, limit):
	async with ShoutsCache.lock:
		return ShoutsCache.top_authors[:limit]


@mutation.field("createShout")
@login_required
async def create_shout(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()

	new_shout = Shout.create(**input)
	ShoutAuthor.create(
		shout = new_shout.id,
		user = user_id)

	task = GitTask(
		input,
		user.username,
		user.email,
		"new shout %s" % (new_shout.slug)
		)

	return {
		"shout" : new_shout
	}

@mutation.field("updateShout")
@login_required
async def update_shout(_, info, id, input):
	auth = info.context["request"].auth
	user_id = auth.user_id

	session = local_session()
	user = session.query(User).filter(User.id == user_id).first()
	shout = session.query(Shout).filter(Shout.id == id).first()

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

	for topic in input.get("topics"):
		ShoutTopic.create(
			shout = shout.id,
			topic = topic)

	task = GitTask(
		input,
		user.username,
		user.email,
		"update shout %s" % (shout.slug)
		)

	return {
		"shout" : shout
	}

@mutation.field("rateShout")
@login_required
async def rate_shout(_, info, shout_id, value):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		rating = session.query(ShoutRating).\
			filter(and_(ShoutRating.rater_id == user_id, ShoutRating.shout_id == shout_id)).first()
		if rating:
			rating.value = value;
			rating.ts = datetime.now()
			session.commit()
		else:
			rating = ShoutRating.create(
				rater_id = user_id,
				shout_id = shout_id,
				value = value
			)

	await ShoutRatingStorage.update_rating(rating)

	return {"error" : ""}

@mutation.field("viewShout")
async def view_shout(_, info, shout_id):
	await ShoutViewStorage.inc_view(shout_id)
	return {"error" : ""}

@query.field("getShoutBySlug")
async def get_shout_by_slug(_, info, slug):
	slug_fields = [node.name.value for node in info.field_nodes[0].selection_set.selections]
	slug_fields = set(["authors", "comments", "topics"]).intersection(slug_fields)
	select_options = [selectinload(getattr(Shout, field)) for field in slug_fields]

	with local_session() as session:
		shout = session.query(Shout).\
			options(select_options).\
			filter(Shout.slug == slug).first()
	shout.rating = await ShoutRatingStorage.get_rating(shout.id)
	shout.views = await ShoutViewStorage.get_view(shout.id)
	return shout
