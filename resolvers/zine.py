from orm import Shout, ShoutAuthor, ShoutTopic, ShoutRating, ShoutViewByDay, User, Community, Resource
from orm.base import local_session

from resolvers.base import mutation, query

from auth.authenticate import login_required
from settings import SHOUTS_REPO

import subprocess
import asyncio
from datetime import datetime, timedelta

from pathlib import Path
from sqlalchemy import select, func, desc

class GitTask:

	queue = asyncio.Queue()

	def __init__(self, input, username, user_email, comment):
		self.slug = input["slug"];
		self.shout_body = input["body"];
		self.username = username;
		self.user_email = user_email;
		self.comment = comment;

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


class TopShouts:
	limit = 50
	period = 60*60 #1 hour

	lock = asyncio.Lock()

	@staticmethod
	async def prepare_shouts_by_rating():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutRating.value).label("rating")).\
				join(ShoutRating).\
				where(ShoutRating.ts > month_ago).\
				group_by(Shout.id).\
				order_by(desc("rating")).\
				limit(TopShouts.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = row.rating
				shouts.append(shout)
		async with TopShouts.lock:
			TopShouts.shouts_by_rating = shouts

	@staticmethod
	async def prepare_favorites_shouts():
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutRating.value).label("rating")).\
				join(ShoutRating).\
				group_by(Shout.id).\
				order_by(desc("rating")).\
				limit(TopShouts.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.rating = row.rating
				shouts.append(shout)
		async with TopShouts.lock:
			TopShouts.favorites_shouts = shouts

	@staticmethod
	async def prepare_shouts_by_view():
		month_ago = datetime.now() - timedelta(days = 30)
		with local_session() as session:
			stmt = select(Shout, func.sum(ShoutViewByDay.value).label("view")).\
				join(ShoutViewByDay).\
				where(ShoutViewByDay.day > month_ago).\
				group_by(Shout.id).\
				order_by(desc("view")).\
				limit(TopShouts.limit)
			shouts = []
			for row in session.execute(stmt):
				shout = row.Shout
				shout.view = row.view
				shouts.append(shout)
		async with TopShouts.lock:
			TopShouts.shouts_by_view = shouts

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
				limit(TopShouts.limit)
			authors = {}
			for row in session.execute(stmt):
				authors[row.user] = row.view
			authors_ids = authors.keys()
			authors = session.query(User).filter(User.id.in_(authors_ids)).all()
		async with TopShouts.lock:
			TopShouts.top_authors = authors


	@staticmethod
	async def worker():
		print("top shouts worker start")
		while True:
			try:
				print("top shouts: update cache")
				await TopShouts.prepare_favorites_shouts()
				await TopShouts.prepare_shouts_by_rating()
				await TopShouts.prepare_shouts_by_view()
				await TopShouts.prepare_top_authors()
				print("top shouts: update finished")
			except Exception as err:
				print("top shouts worker error = %s" % (err))
			await asyncio.sleep(TopShouts.period)


@query.field("topShoutsByView")
async def top_shouts_by_view(_, info, limit):
	async with TopShouts.lock:
		return TopShouts.shouts_by_view[:limit]


@query.field("topShoutsByRating")
async def top_shouts_by_rating(_, info, limit):
	async with TopShouts.lock:
		return TopShouts.shouts_by_rating[:limit]


@query.field("favoritesShouts")
async def favorites_shouts(_, info, limit):
	async with TopShouts.lock:
		return TopShouts.favorites_shouts[:limit]


@query.field("topAuthors")
async def top_authors(_, info, limit):
	async with TopShouts.lock:
		return TopShouts.top_authors[:limit]


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

# TODO: get shout with comments query

@query.field("getShout")  #FIXME: add shout joined with comments
async def get_shout(_, info, shout_id):
	month_ago = datetime.now() - timedelta(days = 30)
	with local_session() as session:
		stmt = select(Comment, func.sum(CommentRating.value).label("rating")).\
			join(CommentRating).\
			where(CommentRating.ts > month_ago).\
			where(Comment.shout == shout_id).\
			# join(ShoutComment)
			group_by(Shout.id).\
			order_by(desc("rating")).\
			limit(limit)
		shouts = []
		for row in session.execute(stmt):
			shout = row.Shout
			shout.rating = row.rating
			shout.comments
			shouts.append(shout)
	return shout