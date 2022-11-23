import json
from datetime import datetime, timedelta, timezone

from auth.authenticate import login_required
from base.redis import redis
from base.orm import local_session
from base.resolvers import query
from orm.user import User
from resolvers.zine.profile import followed_authors
from .unread import get_unread_counter


async def load_messages(chatId: str, limit: int, offset: int):
    ''' load :limit messages for :chatId with :offset '''
    messages = []
    message_ids = await redis.lrange(
        f"chats/{chatId}/message_ids", 0 - offset - limit, 0 - offset
    )
    if message_ids:
        message_keys = [
            f"chats/{chatId}/messages/{mid}" for mid in message_ids
        ]
        messages = await redis.mget(*message_keys)
        messages = [json.loads(msg) for msg in messages]
    return {
        "messages": messages,
        "error": None
    }


@query.field("loadChats")
@login_required
async def load_chats(_, info, limit: int, offset: int):
    """ load :limit chats of current user with :offset """
    user = info.context["request"].user
    if user:
        chats = await redis.execute("GET", f"chats_by_user/{user.slug}")
        if chats:
            chats = list(json.loads(chats))[offset:offset + limit]
        if not chats:
            chats = []
        for c in chats:
            c['messages'] = await load_messages(c['id'], limit, offset)
            c['unread'] = await get_unread_counter(c['id'], user.slug)
        return {
            "chats": chats,
            "error": None
        }
    else:
        return {
            "error": "please login",
            "chats": []
        }


@query.field("loadMessagesBy")
@login_required
async def load_messages_by(_, info, by, limit: int = 50, offset: int = 0):
    ''' load :amolimitunt messages of :chat_id with :offset '''
    user = info.context["request"].user
    my_chats = await redis.execute("GET", f"chats_by_user/{user.slug}")
    chat_id = by.get('chat')
    if chat_id:
        chat = await redis.execute("GET", f"chats/{chat_id}")
        if not chat:
            return {
                "error": "chat not exist"
            }
        messages = await load_messages(chat_id, limit, offset)
    user_id = by.get('author')
    if user_id:
        chats = await redis.execute("GET", f"chats_by_user/{user_id}")
        our_chats = list(set(chats) & set(my_chats))
        for c in our_chats:
            messages += await load_messages(c, limit, offset)
    body_like = by.get('body')
    if body_like:
        for c in my_chats:
            mmm = await load_messages(c, limit, offset)
            for m in mmm:
                if body_like in m["body"]:
                    messages.append(m)
    days = by.get("days")
    if days:
        messages = filter(
            lambda m: datetime.now(tz=timezone.utc) - int(m["createdAt"]) < timedelta(days=by.get("days")),
            messages
        )
    return {
        "messages": messages,
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
