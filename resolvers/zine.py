from orm import Shout, User
from orm.base import local_session

from resolvers.base import mutation, query

from auth.authenticate import login_required
from settings import SHOUTS_REPO

import subprocess

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
	
	new_shout = Shout.create(
		author_id = user_id,
		body = body
		)
	
	branch_name = "shout%s" % (new_shout.id)
	
	cmd = "cd %s; git checkout master && git checkout -b %s && git branch %s-dev" % (SHOUTS_REPO, branch_name, branch_name)
	output = subprocess.check_output(cmd, shell=True)
	print(output)
	
	shout_filename = "%s/body" % (SHOUTS_REPO)
	with open(shout_filename, mode='w', encoding='utf-8') as shout_file:
		shout_file.write(body)
	
	cmd = "cd %s; git commit -a -m 'initial version'" % (SHOUTS_REPO)
	output = subprocess.check_output(cmd, shell=True)
	print(output)
	
	return {
		"shout" : new_shout
	}


# TODO: paginate, get, update, delete
