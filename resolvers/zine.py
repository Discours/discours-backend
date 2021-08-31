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


@query.field("topShoutsByView")
async def top_shouts_by_view(_, info, limit):
	month_ago = datetime.now() - timedelta(days = 30)
	with local_session() as session:
		stmt = select(Shout, func.sum(ShoutViewByDay.value).label("view")).\
			join(ShoutViewByDay).\
			where(ShoutViewByDay.day > month_ago).\
			group_by(Shout.id).\
			order_by(desc("view")).\
			limit(limit)
		shouts = []
		for row in session.execute(stmt):
			shout = row.Shout
			shout.view = row.view
			shouts.append(shout)
	return shouts


@query.field("topShoutsByRating")
async def top_shouts(_, info, limit):
	month_ago = datetime.now() - timedelta(days = 30)
	with local_session() as session:
		stmt = select(Shout, func.sum(ShoutRating.value).label("rating")).\
			join(ShoutRating).\
			where(ShoutRating.ts > month_ago).\
			group_by(Shout.id).\
			order_by(desc("rating")).\
			limit(limit)
		shouts = []
		for row in session.execute(stmt):
			shout = row.Shout
			shout.rating = row.rating
			shouts.append(shout)
	return shouts


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

# TODO: paginate, get, update, delete
