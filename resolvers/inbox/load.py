import json
from datetime import datetime, timedelta, timezone

from auth.authenticate import login_required
from base.redis import redis
from base.orm import local_session
from base.resolvers import query
from base.exceptions import ObjectNotExist
from orm.user import User
from resolvers.zine.profile import followed_authors
from .unread import get_unread_counter


async def load_messages(chat_id: str, limit: int, offset: int):
    ''' load :limit messages for :chat_id with :offset '''
    messages = []
    message_ids = await redis.lrange(
        f"chats/{chat_id}/message_ids", offset + limit, offset
    )
    if message_ids:
        message_keys = [
            f"chats/{chat_id}/messages/{mid}" for mid in message_ids
        ]
        messages = await redis.mget(*message_keys)
        messages = [json.loads(msg) for msg in messages]
    return messages


@query.field("loadChats")
@login_required
async def load_chats(_, info, limit: int = 50, offset: int = 0):
    """ load :limit chats of current user with :offset """
    user = info.context["request"].user
    print('[inbox] load user\'s chats')
    cids = await redis.execute("SMEMBERS", "chats_by_user/" + user.slug)
    if cids:
        cids = list(cids)[offset:offset + limit]
    if not cids:
        print('[inbox.load] no chats were found')
        cids = []
    chats = []
    for cid in cids:
        c = await redis.execute("GET", "chats/" + cid.decode("utf-8"))
        if c:
            c = dict(json.loads(c))
            c['messages'] = await load_messages(cid, 50, 0)
            c['unread'] = await get_unread_counter(cid, user.slug)
            with local_session() as session:
                c['members'] = []
                for user in c["users"]:
                    a = session.query(User).where(User.slug == user).first().dict()
                    c['members'].append({
                        "slug": user,
                        "userpic": a["userpic"],
                        "name": a["name"],
                        "lastSeen": a["lastSeen"],
                    })
                del c["users"]
            chats.append(c)
    return {
        "chats": chats,
        "error": None
    }


@query.field("loadMessagesBy")
@login_required
async def load_messages_by(_, info, by, limit: int = 50, offset: int = 0):
    ''' load :amolimitunt messages of :chat_id with :offset '''
    messages = set([])
    by_chat = by.get('chat')
    if by_chat:
        chat = await redis.execute("GET", f"chats/{by_chat}")
        if not chat:
            raise ObjectNotExist("Chat not exists")
        # everyone's messages in filtered chat
        messages.union(set(await load_messages(by_chat, limit, offset)))

    cids = set([])
    by_author = by.get('author')
    body_like = by.get('body')
    user = info.context["request"].user
    if user:
        cids.unioin(set(await redis.execute("SMEMBERS", "chats_by_user/" + user.slug)))
    if len(messages) == 0:
        if by_author:
            # all author's messages
            cids.union(set(await redis.execute("SMEMBERS", f"chats_by_user/{by_author}")))
            if by_chat:
                # author's messages in filtered chat
                messages.union(set(filter(lambda m: m["author"] == by_author, list(messages))))
        for c in cids:
            messages.union(set(await load_messages(c, limit, offset)))
        if body_like:
            # search in all messages in all user's chats
            for c in cids:
                mmm = set(await load_messages(c, limit, offset))
                for m in mmm:
                    if body_like in m["body"]:
                        messages.add(m)
            else:
                # search in chat's messages
                messages.union(set(filter(lambda m: body_like in m["body"], list(messages))))

    days = by.get("days")
    if days:
        messages.union(set(filter(
            lambda m: datetime.now(tz=timezone.utc) - int(m["createdAt"]) < timedelta(days=by.get("days")),
            messages
        )))
    return {
        "messages": sorted(list(messages)),
        "error": None
    }


@query.field("loadRecipients")
async def load_recipients(_, info, limit=50, offset=0):
    chat_users = []
    user = info.context["request"].user
    try:
        chat_users += await followed_authors(user.slug)
        limit = limit - len(chat_users)
    except Exception:
        pass
    with local_session() as session:
        chat_users += session.query(User).where(User.emailConfirmed).limit(limit).offset(offset)
    return {
        "members": chat_users,
        "error": None
    }
