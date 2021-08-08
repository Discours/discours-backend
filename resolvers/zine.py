from orm import Shout, User
from orm.base import local_session

from resolvers.base import mutation, query

from auth.authenticate import login_required
from settings import SHOUTS_REPO

import subprocess
import asyncio

class GitTask:

	queue = asyncio.Queue()

	def __init__(self, shout_id, shout_body, username, user_email, comment):
		self.shout_id = shout_id;
		self.shout_body = shout_body;
		self.username = username;
		self.user_email = user_email;
		self.comment = comment;

		GitTask.queue.put_nowait(self)

	def execute(self):
		cmd = "cd %s; git checkout master" % (SHOUTS_REPO)
		output = subprocess.check_output(cmd, shell=True)
		print(output)

		shout_filename = "shout%s.md" % (self.shout_id)
		shout_full_filename = "%s/%s" % (SHOUTS_REPO, shout_filename)
		with open(shout_full_filename, mode='w', encoding='utf-8') as shout_file:
			shout_file.write(self.shout_body)

		author = "%s <%s>" % (self.username, self.user_email)
		cmd = "cd %s; git add %s; git commit -m '%s' --author='%s'" % \
			(SHOUTS_REPO, shout_filename, self.comment, author)
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
async def create_shout(_, info, body):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
	
	new_shout = Shout.create(
		author_id = user_id,
		body = body
		)

	task = GitTask(
		new_shout.id,
		body,
		user.username,
		user.email,
		"new shout %s" % (new_shout.id)
		)

	return {
		"shout" : new_shout
	}


# TODO: paginate, get, update, delete
