from orm import Shout, User
from orm.base import global_session

from resolvers.base import mutation, query, subscription

@query.field("topShouts")
async def top_shouts(_, info: GraphQLResolveInfo):
    # TODO: implement top shouts 
    pass


@query.field("topAuthors")
async def top_shouts(_, info: GraphQLResolveInfo):
    # TODO: implement top authors 
    pass


# TODO: debug me
@mutation.field("createShout")
@login_required
async def create_post(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	new_shout = Shout.create(
		author = user_id,
		body = input["body"], # TODO: add createShoutInput in scheme.graphql
		title = input.get("title")
        # TODO: generate slug
		)
	
	return {
		"status": True,
		"shout" : new_shout
	}


# TODO: paginate, get, update, delete