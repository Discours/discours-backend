import subprocess
from pathlib import Path
import asyncio
from settings import SHOUTS_REPO

class GitTask:
	''' every shout update use a new task '''
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
		print("[resolvers.git] worker start")
		while True:
			task = await GitTask.queue.get()
			try:
				task.execute()
			except Exception as err:
				print("[resolvers.git] worker error: %s" % (err))
