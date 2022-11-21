from auth.authenticate import login_required
from base.resolvers import mutation
# from resolvers.community import community_follow, community_unfollow
from resolvers.zine.profile import author_follow, author_unfollow
from resolvers.zine.reactions import reactions_follow, reactions_unfollow
from resolvers.zine.topics import topic_follow, topic_unfollow


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    user = info.context["request"].user
    try:
        if what == "AUTHOR":
            author_follow(user, slug)
        elif what == "TOPIC":
            topic_follow(user, slug)
        elif what == "COMMUNITY":
            # community_follow(user, slug)
            pass
        elif what == "REACTIONS":
            reactions_follow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    user = info.context["request"].user

    try:
        if what == "AUTHOR":
            author_unfollow(user, slug)
        elif what == "TOPIC":
            topic_unfollow(user, slug)
        elif what == "COMMUNITY":
            # community_unfollow(user, slug)
            pass
        elif what == "REACTIONS":
            reactions_unfollow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}
