import json

from base.redis import redis


async def get_unread_counter(chat_id: str, user_slug: str):
    try:
        return int(await redis.execute("LLEN", f"chats/{chat_id}/unread/{user_slug}"))
    except Exception:
        return 0


async def get_total_unread_counter(user_slug: str):
    chats = await redis.execute("GET", f"chats_by_user/{user_slug}")
    if not chats:
        return 0

    chats = json.loads(chats)
    unread = 0
    for chat_id in chats:
        n = await get_unread_counter(chat_id, user_slug)
        unread += n

    return unread


async def load_user_chats(slug, offset: int, amount: int):
    """ load :amount chats of :slug user with :offset """

    chats = await redis.execute("GET", f"chats_by_user/{slug}")
    if chats:
        chats = list(json.loads(chats))[offset:offset + amount]
    if not chats:
        chats = []
    for c in chats:
        c['messages'] = await load_messages(c['id'])
        c['unread'] = await get_unread_counter(c['id'], slug)
    return {
        "chats": chats,
        "error": None
    }


async def load_messages(chatId: str, offset: int, amount: int):
    ''' load :amount messages for :chatId with :offset '''
    messages = []
    message_ids = await redis.lrange(
        f"chats/{chatId}/message_ids", 0 - offset - amount, 0 - offset
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
