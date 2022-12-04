import json
from datetime import datetime, timedelta, timezone

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.redis import redis
from base.orm import local_session
from base.resolvers import query
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
    auth: AuthCredentials = info.context["request"].auth

    cids = await redis.execute("SMEMBERS", "chats_by_user/" + str(auth.user_id))
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
            c['messages'] = await load_messages(cid, 5, 0)
            c['unread'] = await get_unread_counter(cid, auth.user_id)
            with local_session() as session:
                c['members'] = []
                for uid in c["users"]:
                    a = session.query(User).where(User.id == uid).first()
                    if a:
                        c['members'].append({
                            "id": a.id,
                            "slug": a.slug,
                            "userpic": a.userpic,
                            "name": a.name,
                            "lastSeen": a.lastSeen,
                        })
                        chats.append(c)
    return {
        "chats": chats,
        "error": None
    }


async def search_user_chats(by, messages: set, user_id: int, limit, offset):
    cids = set([])
    by_author = by.get('author')
    body_like = by.get('body')
    cids.unioin(set(await redis.execute("SMEMBERS", "chats_by_user/" + str(user_id))))
    if by_author:
        # all author's messages
        cids.union(set(await redis.execute("SMEMBERS", f"chats_by_user/{by_author}")))
        # author's messages in filtered chat
        messages.union(set(filter(lambda m: m["author"] == by_author, list(messages))))
        for c in cids:
            messages.union(set(await load_messages(c, limit, offset)))
    if body_like:
        # search in all messages in all user's chats
        for c in cids:
            # FIXME: user redis scan here
            mmm = set(await load_messages(c, limit, offset))
            for m in mmm:
                if body_like in m["body"]:
                    messages.add(m)
        else:
            # search in chat's messages
            messages.union(set(filter(lambda m: body_like in m["body"], list(messages))))
    return messages


@query.field("loadMessagesBy")
@login_required
async def load_messages_by(_, info, by, limit: int = 10, offset: int = 0):
    ''' load :limit messages of :chat_id with :offset '''
    messages = set([])
    by_chat = by.get('chat')
    if by_chat:
        chat = await redis.execute("GET", f"chats/{by_chat}")
        if not chat:
            return {
                "messages": [],
                "error": "chat not exist"
            }
        # everyone's messages in filtered chat
        messages.union(set(await load_messages(by_chat, limit, offset)))

    auth: AuthCredentials = info.context["request"].auth

    if len(messages) == 0:
        # FIXME
        messages.union(search_user_chats(by, messages, auth.user_id, limit, offset))

    days = by.get("days")
    if days:
        messages.union(set(filter(
            lambda m: datetime.now(tz=timezone.utc) - int(m["createdAt"]) < timedelta(days=by.get("days")),
            list(messages)
        )))
    return {
        "messages": sorted(
            lambda m: m.createdAt,
            list(messages)
        ),
        "error": None
    }


@query.field("loadRecipients")
async def load_recipients(_, info, limit=50, offset=0):
    chat_users = []
    auth: AuthCredentials = info.context["request"].auth

    try:
        chat_users += await followed_authors(auth.user_id)
        limit = limit - len(chat_users)
    except Exception:
        pass
    with local_session() as session:
        chat_users += session.query(User).where(User.emailConfirmed).limit(limit).offset(offset)
    return {
        "members": chat_users,
        "error": None
    }
