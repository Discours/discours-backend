import json

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import query
from base.orm import local_session
from orm.user import AuthorFollower


@query.field("searchUsers")
@login_required
async def search_users(_, info, query: str, offset: int = 0, amount: int = 50):
    result = []
    # TODO: maybe redis scan?
    user = info.context["request"].user
    talk_before = await redis.execute("GET", f"/chats_by_user/{user.slug}")
    if talk_before:
        talk_before = list(json.loads(talk_before))[offset:offset + amount]
        for chat_id in talk_before:
            members = await redis.execute("GET", f"/chats/{chat_id}/users")
            if members:
                members = list(json.loads(members))
                for member in members:
                    if member.startswith(query):
                        if member not in result:
                            result.append(member)
    user = info.context["request"].user

    more_amount = amount - len(result)

    with local_session() as session:
        # followings
        result += session.query(AuthorFollower.author).where(AuthorFollower.follower.startswith(query))\
            .offset(offset + len(result)).limit(more_amount)

        more_amount = amount
        # followers
        result += session.query(AuthorFollower.follower).where(AuthorFollower.author.startswith(query))\
            .offset(offset + len(result)).limit(offset + len(result) + amount)
    return {
        "slugs": list(result),
        "error": None
    }


@query.field("searchChats")
@login_required
async def search_chats(_, info, query: str, offset: int = 0, amount: int = 50):
    user = info.context["request"].user
    my_chats = await redis.execute("GET", f"/chats_by_user/{user.slug}")
    chats = []
    for chat_id in my_chats:
        chat = await redis.execute("GET", f"chats/{chat_id}")
        if chat:
            chat = dict(json.loads(chat))
            chats.append(chat)
    return {
        "chats": chats,
        "error": None
    }


@query.field("searchMessages")
@login_required
async def search_messages(_, info, query: str, offset: int = 0, amount: int = 50):
    user = info.context["request"].user
    my_chats = await redis.execute("GET", f"/chats_by_user/{user.slug}")
    chats = []
    if my_chats:
        my_chats = list(json.loads(my_chats))
        for chat_id in my_chats:
            chat = await redis.execute("GET", f"chats/{chat_id}")
            if chat:
                chat = dict(json.loads(chat))
                chats.append(chat)
    return {
        "chats": chats,
        "error": None
    }
