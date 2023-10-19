from base.redis import redis


async def get_unread_counter(chat_id: str, user_id: int):
    try:
        unread = await redis.execute("LLEN", f"chats/{chat_id.decode('utf-8')}/unread/{user_id}")
        if unread:
            return unread
    except Exception:
        return 0
