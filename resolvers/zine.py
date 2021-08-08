from orm import Shout, User
from orm.base import local_session

from resolvers.base import mutation, query

from auth.authenticate import login_required
from settings import SHOUTS_REPO

import subprocess
import asyncio

from pathlib import Path

class GitTask:

	queue = asyncio.Queue()

	def __init__(self, input, username, user_email, comment):
		self.slug = input["slug"];
		self.org = input["org"];
		self.shout_body = input["body"];
		self.username = username;
		self.user_email = user_email;
		self.comment = comment;

		GitTask.queue.put_nowait(self)
	
	def init_repo(self):
		repo_path = "%s/%s" % (SHOUTS_REPO, self.org)
		
		Path(repo_path).mkdir()
		
		cmd = "cd %s && git init && touch initial && git add initial && git commit -m 'init repo'" % (repo_path)
		output = subprocess.check_output(cmd, shell=True)
		print(output)

	def execute(self):
		repo_path = "%s/%s" % (SHOUTS_REPO, self.org)
		
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


@query.field("topShouts")
async def top_shouts(_, info):
    # TODO: implement top shouts 
    pass


@query.field("topAuthors")
async def top_shouts(_, info):
    # TODO: implement top authors 
    pass


@mutation.field("createShout")
@login_required
async def create_shout(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
	
	new_shout = Shout.create(
		slug = input["slug"],
		org = input["org"],
		author_id = user_id,
		body = input["body"],
		replyTo = input.get("replyTo"),
		versionOf = input.get("versionOf"),
		tags = input.get("tags"),
		topics = input.get("topics")
		)

	task = GitTask(
		input,
		user.username,
		user.email,
		"new shout %s" % (new_shout.slug)
		)

	return {
		"shout" : new_shout
	}


# TODO: paginate, get, update, delete
