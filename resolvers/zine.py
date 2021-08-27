from orm import Shout, User, Community, Resource
from orm.base import local_session

from resolvers.base import mutation, query

from auth.authenticate import login_required
from settings import SHOUTS_REPO

import subprocess
import asyncio

from pathlib import Path

class GitTask:

	queue = asyncio.Queue()

	def __init__(self, input, org, username, user_email, comment):
		self.slug = input["slug"];
		self.shout_body = input["body"];
		self.org = org; #FIXME
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
	
	# org_id = org = input["org_id"]
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
		# org = session.query(Organization).filter(Organization.id == org_id).first()
		
	new_shout = Shout.create(
		slug = input["slug"],
		# org_id = org_id,
		authors = [user_id, ],
		body = input["body"],
		replyTo = input.get("replyTo"),
		versionOf = input.get("versionOf"),
		tags = input.get("tags"),
		topics = input.get("topics")
		)

	task = GitTask(
		input,
		org.name,
		user.username,
		user.email,
		"new shout %s" % (new_shout.slug)
		)

	return {
		"shout" : new_shout
	}

@mutation.field("updateShout")
@login_required
async def update_shout(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id

	slug = input["slug"]
	# org_id = org = input["org_id"]
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
		shout = session.query(Shout).filter(Shout.slug == slug).first()
		# org = session.query(Organization).filter(Organization.id == org_id).first()

	if not shout:
		return {
			"error" : "shout not found"
		}

	if shout.authors[0] != user_id:
		scopes = auth.scopes
		print(scopes)
		if not Resource.shout_id in scopes:
			return {
				"error" : "access denied"
			}

	shout.body = input["body"],
	shout.replyTo = input.get("replyTo"),
	shout.versionOf = input.get("versionOf"),
	shout.tags = input.get("tags"),
	shout.topics = input.get("topics")

	with local_session() as session:
		session.commit()

	task = GitTask(
		input,
		org.name,
		user.username,
		user.email,
		"update shout %s" % (shout.slug)
		)

	return {
		"shout" : shout
	}

# TODO: paginate, get, update, delete
