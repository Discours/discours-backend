from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.resolvers import mutation, subscription
# from resolvers.community import community_follow, community_unfollow
from resolvers.zine.profile import author_follow, author_unfollow
from resolvers.zine.reactions import reactions_follow, reactions_unfollow
from resolvers.zine.topics import topic_follow, topic_unfollow
import asyncio
from graphql.type import GraphQLResolveInfo


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    auth: AuthCredentials = info.context["request"].auth

    try:
        if what == "AUTHOR":
            author_follow(auth.user_id, slug)
        elif what == "TOPIC":
            topic_follow(auth.user_id, slug)
        elif what == "COMMUNITY":
            # community_follow(user, slug)
            pass
        elif what == "REACTIONS":
            reactions_follow(auth.user_id, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    auth: AuthCredentials = info.context["request"].auth

    try:
        if what == "AUTHOR":
            author_unfollow(auth.user_id, slug)
        elif what == "TOPIC":
            topic_unfollow(auth.user_id, slug)
        elif what == "COMMUNITY":
            # community_unfollow(user, slug)
            pass
        elif what == "REACTIONS":
            reactions_unfollow(auth.user_id, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}


@subscription.source("newShout")
@login_required
async def shout_generator(_, info: GraphQLResolveInfo):
    print(f"[resolvers.zine] shouts generator {info}")
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id
    try:
        tasks = []

        # TODO: implement when noticing new shout

        while True:
            shout = await asyncio.gather(*tasks)
            yield shout
    finally:
        pass


@subscription.source("newReaction")
@login_required
async def reaction_generator(_, info):
    print(f"[resolvers.zine] reactions generator {info}")
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id
    try:
        tasks = []

        # TODO: implement when noticing new reaction

        while True:
            reaction = await asyncio.gather(*tasks)
            yield reaction
    finally:
        pass
