from services.schema import mutation
from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from resolvers.profile import author_follow, author_unfollow
from resolvers.reactions import reactions_follow, reactions_unfollow
from resolvers.topics import topic_follow, topic_unfollow
from services.following import FollowingManager, FollowingResult
from resolvers.community import community_follow, community_unfollow
from services.presence import notify_follower
from orm.user import User
from services.db import local_session


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    auth: AuthCredentials = info.context["request"].auth

    try:
        if what == "AUTHOR":
            if author_follow(auth.user_id, slug):
                result = FollowingResult("NEW", "author", slug)
                await FollowingManager.push("author", result)
                with local_session() as session:
                    author = session.query(User.id).where(User.slug == slug).one()
                    follower = session.query(User.id).where(User.id == auth.user_id).one()
                    notify_follower(follower.dict(), author.id)
        elif what == "TOPIC":
            if topic_follow(auth.user_id, slug):
                result = FollowingResult("NEW", "topic", slug)
                await FollowingManager.push("topic", result)
        elif what == "COMMUNITY":
            if community_follow(auth.user_id, slug):
                result = FollowingResult("NEW", "community", slug)
                await FollowingManager.push("community", result)
        elif what == "REACTIONS":
            if reactions_follow(auth.user_id, slug):
                result = FollowingResult("NEW", "shout", slug)
                await FollowingManager.push("shout", result)
    except Exception as e:
        print(Exception(e))
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    auth: AuthCredentials = info.context["request"].auth

    try:
        if what == "AUTHOR":
            if author_unfollow(auth.user_id, slug):
                result = FollowingResult("DELETED", "author", slug)
                await FollowingManager.push("author", result)
        elif what == "TOPIC":
            if topic_unfollow(auth.user_id, slug):
                result = FollowingResult("DELETED", "topic", slug)
                await FollowingManager.push("topic", result)
        elif what == "COMMUNITY":
            if community_unfollow(auth.user_id, slug):
                result = FollowingResult("DELETED", "community", slug)
                await FollowingManager.push("community", result)
        elif what == "REACTIONS":
            if reactions_unfollow(auth.user_id, slug):
                result = FollowingResult("DELETED", "shout", slug)
                await FollowingManager.push("shout", result)
    except Exception as e:
        return {"error": str(e)}

    return {}
