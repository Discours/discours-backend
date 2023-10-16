import json

from services.redis import redis


async def get_unread_counter(chat_id: str, author_id: int) -> int:
    unread = await redis.execute("LLEN", f"chats/{chat_id}/unread/{author_id}")
    return unread or 0


async def get_total_unread_counter(author_id: int) -> int:
    chats = await redis.execute("GET", f"chats_by_author/{author_id}")
    unread = 0
    if chats:
        chats = json.loads(chats)
        for chat_id in chats:
            n = await get_unread_counter(chat_id.decode("utf-8"), author_id)
            unread += n
    return unread
