from base.redis import redis
import json


async def get_unread_counter(chat_id: str, user_slug: str):
    try:
        unread = await redis.execute("LLEN", f"chats/{chat_id}/unread/{user_slug}")
        if unread:
            return unread
    except Exception:
        return 0


async def get_total_unread_counter(user_slug: str):
    chats = await redis.execute("GET", f"chats_by_user/{user_slug}")
    unread = 0
    if chats:
        chats = json.loads(chats)
        for chat_id in chats:
            n = await get_unread_counter(chat_id.decode('utf-8'), user_slug)
            unread += n
    return unread
