from services.redis import redis
import json


async def get_unread_counter(chat_id: str, author_id: int):
    try:
        unread = await redis.execute(
            "LLEN", f"chats/{chat_id}/unread/{author_id}"
        )
        if unread:
            return unread
    except Exception:
        return 0


async def get_total_unread_counter(author_id: int):
    print(f"[services.unread] get_total_unread_counter({author_id})")
    chats = await redis.execute("SMEMBERS", f"chats_by_author/{author_id}")
    unread = 0
    for chat_id in list(chats):
        n = await get_unread_counter(chat_id.decode("utf-8"), author_id)
        unread += n
    return unread
