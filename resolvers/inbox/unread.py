from base.redis import redis
import json


async def get_unread_counter(chat_id: str, user_id: int):
    try:
        unread = await redis.execute("LLEN", f"chats/{chat_id}/unread/{user_id}")
        if unread:
            return unread
    except Exception:
        return 0


async def get_total_unread_counter(user_id: int):
    chats = await redis.execute("GET", f"chats_by_user/{str(user_id)}")
    unread = 0
    if chats:
        chats = json.loads(chats)
        for chat_id in chats:
            n = await get_unread_counter(chat_id.decode('utf-8'), user_id)
            unread += n
    return unread
