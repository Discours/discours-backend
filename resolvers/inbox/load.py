import json
# from datetime import datetime, timedelta, timezone

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.redis import redis
from base.orm import local_session
from base.resolvers import query
from orm.user import User
from resolvers.zine.profile import followed_authors
from .unread import get_unread_counter


async def load_messages(chat_id: str, limit: int = 5, offset: int = 0, ids=[]):
    ''' load :limit messages for :chat_id with :offset '''
    messages = []
    message_ids = []
    if ids:
        message_ids += ids
    try:
        if limit:
            message_ids = await redis.lrange(f"chats/{chat_id}/message_ids",
                                             offset,
                                             offset + limit
                                             )
    except Exception as e:
        print(e)
    if message_ids:
        message_keys = [
            f"chats/{chat_id}/messages/{mid.decode('utf-8')}" for mid in message_ids
        ]
        messages = await redis.mget(*message_keys)
        messages = [json.loads(msg.decode('utf-8')) for msg in messages]
        replies = []
        for m in messages:
            rt = m.get('replyTo')
            if rt:
                rt = int(rt)
                if rt not in message_ids:
                    replies.append(rt)
        if replies:
            messages += await load_messages(chat_id, limit=0, ids=replies)
    return messages


@query.field("loadChats")
@login_required
async def load_chats(_, info, limit: int = 50, offset: int = 0):
    """ load :limit chats of current user with :offset """
    auth: AuthCredentials = info.context["request"].auth

    cids = await redis.execute("SMEMBERS", "chats_by_user/" + str(auth.user_id))
    onliners = await redis.execute("SMEMBERS", "users-online")
    if cids:
        cids = list(cids)[offset:offset + limit]
    if not cids:
        print('[inbox.load] no chats were found')
        cids = []
    chats = []
    for cid in cids:
        cid = cid.decode("utf-8")
        c = await redis.execute("GET", "chats/" + cid)
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
                            "online": a.id in onliners
                        })
                chats.append(c)
    return {
        "chats": chats,
        "error": None
    }


@query.field("loadMessagesBy")
@login_required
async def load_messages_by(_, info, by, limit: int = 10, offset: int = 0):
    ''' load :limit messages of :chat_id with :offset '''

    auth: AuthCredentials = info.context["request"].auth
    userchats = await redis.execute("SMEMBERS", "chats_by_user/" + str(auth.user_id))
    userchats = [c.decode('utf-8') for c in userchats]
    # print('[inbox] userchats: %r' % userchats)
    if userchats:
        # print('[inbox] loading messages by...')
        messages = []
        by_chat = by.get('chat')
        if by_chat in userchats:
            chat = await redis.execute("GET", f"chats/{by_chat}")
            # print(chat)
            if not chat:
                return {
                    "messages": [],
                    "error": "chat not exist"
                }
            # everyone's messages in filtered chat
            messages = await load_messages(by_chat, limit, offset)
        return {
            "messages": sorted(
                list(messages),
                key=lambda m: m['createdAt']
            ),
            "error": None
        }
    else:
        return {
            "error": "Cannot access messages of this chat"
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
