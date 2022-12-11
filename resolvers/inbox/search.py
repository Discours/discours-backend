import json
from datetime import datetime, timezone, timedelta
from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.redis import redis
from base.resolvers import query
from base.orm import local_session
from orm.user import AuthorFollower, User
from resolvers.inbox.load import load_messages


@query.field("searchRecipients")
@login_required
async def search_recipients(_, info, query: str, limit: int = 50, offset: int = 0):
    result = []
    # TODO: maybe redis scan?
    auth: AuthCredentials = info.context["request"].auth
    talk_before = await redis.execute("GET", f"/chats_by_user/{auth.user_id}")
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

    more_amount = limit - len(result)

    with local_session() as session:
        # followings
        result += session.query(AuthorFollower.author).join(
            User, User.id == AuthorFollower.follower
        ).where(
            User.slug.startswith(query)
        ).offset(offset + len(result)).limit(more_amount)

        more_amount = limit
        # followers
        result += session.query(AuthorFollower.follower).join(
            User, User.id == AuthorFollower.author
        ).where(
            User.slug.startswith(query)
        ).offset(offset + len(result)).limit(offset + len(result) + limit)
    return {
        "members": list(result),
        "error": None
    }


@query.field("searchMessages")
@login_required
async def search_user_chats(by, messages, user_id: int, limit, offset):
    cids = set([])
    cids.union(set(await redis.execute("SMEMBERS", "chats_by_user/" + str(user_id))))
    messages = []

    by_author = by.get('author')
    if by_author:
        # all author's messages
        cids.union(set(await redis.execute("SMEMBERS", f"chats_by_user/{by_author}")))
        # author's messages in filtered chat
        messages.union(set(filter(lambda m: m["author"] == by_author, list(messages))))
        for c in cids:
            c = c.decode('utf-8')
            messages = await load_messages(c, limit, offset)

    body_like = by.get('body')
    if body_like:
        # search in all messages in all user's chats
        for c in cids:
            # FIXME: use redis scan here
            c = c.decode('utf-8')
            mmm = await load_messages(c, limit, offset)
            for m in mmm:
                if body_like in m["body"]:
                    messages.add(m)
        else:
            # search in chat's messages
            messages.extend(filter(lambda m: body_like in m["body"], list(messages)))

    days = by.get("days")
    if days:
        messages.extend(filter(
            list(messages),
            key=lambda m: (
                datetime.now(tz=timezone.utc) - int(m["createdAt"]) < timedelta(days=by["days"])
            )
        ))
    return {
        "messages": messages,
        "error": None
    }
