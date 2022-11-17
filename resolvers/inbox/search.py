import json

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import query
from base.orm import local_session
from orm.user import AuthorFollower


@query.field("searchUsers")
@login_required
async def search_users(_, info, query: str, limit: int = 50, offset: int = 0):
    result = []
    # TODO: maybe redis scan?
    user = info.context["request"].user
    talk_before = await redis.execute("GET", f"/chats_by_user/{user.slug}")
    if talk_before:
        talk_before = list(json.loads(talk_before))[offset:offset + limit]
        for chat_id in talk_before:
            members = await redis.execute("GET", f"/chats/{chat_id}/users")
            if members:
                members = list(json.loads(members))
                for member in members:
                    if member.startswith(query):
                        if member not in result:
                            result.append(member)
    user = info.context["request"].user

    more_amount = limit - len(result)

    with local_session() as session:
        # followings
        result += session.query(AuthorFollower.author).where(AuthorFollower.follower.startswith(query))\
            .offset(offset + len(result)).limit(more_amount)

        more_amount = limit
        # followers
        result += session.query(AuthorFollower.follower).where(AuthorFollower.author.startswith(query))\
            .offset(offset + len(result)).limit(offset + len(result) + limit)
    return {
        "slugs": list(result),
        "error": None
    }
