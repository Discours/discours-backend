import asyncio
import json
from datetime import datetime

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import mutation, query, subscription
from services.inbox import ChatFollowing, MessageResult, MessagesStorage
from resolvers.inbox.chats import get_chats_by_user


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


@query.field("loadMessages")
@login_required
async def load_chat_messages(_, info, chat_id: str, offset: int = 0, amount: int = 50):
    ''' load [amount] chat's messages with [offset] '''
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    messages = await load_messages(chat_id, offset, amount)
    return {
        "messages": messages,
        "error": None
    }


@mutation.field("createMessage")
@login_required
async def create_message(_, info, chat_id: str, body: str, replyTo=None):
    """ create message with :body for :chat_id replying to :replyTo optionally """
    user = info.context["request"].user
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    message_id = await redis.execute("GET", f"chats/{chat_id}/next_message_id")
    message_id = int(message_id)
    new_message = {
        "chatId": chat_id,
        "id": message_id,
        "author": user.slug,
        "body": body,
        "replyTo": replyTo,
        "createdAt": int(datetime.now().timestamp()),
    }
    await redis.execute(
        "SET", f"chats/{chat_id}/messages/{message_id}", json.dumps(new_message)
    )
    await redis.execute("LPUSH", f"chats/{chat_id}/message_ids", str(message_id))
    await redis.execute("SET", f"chats/{chat_id}/next_message_id", str(message_id + 1))

    chat = json.loads(chat)
    users = chat["users"]
    for user_slug in users:
        await redis.execute(
            "LPUSH", f"chats/{chat_id}/unread/{user_slug}", str(message_id)
        )

    result = MessageResult("NEW", new_message)
    await MessagesStorage.put(result)

    return {
        "message": new_message,
        "error": None
    }


@mutation.field("updateMessage")
@login_required
async def update_message(_, info, chat_id: str, message_id: int, body: str):
    user = info.context["request"].user

    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {"error": "chat not exist"}

    message = await redis.execute("GET", f"chats/{chat_id}/messages/{message_id}")
    if not message:
        return {"error": "message  not exist"}

    message = json.loads(message)
    if message["author"] != user.slug:
        return {"error": "access denied"}

    message["body"] = body
    message["updatedAt"] = int(datetime.now().timestamp())

    await redis.execute("SET", f"chats/{chat_id}/messages/{message_id}", json.dumps(message))

    result = MessageResult("UPDATED", message)
    await MessagesStorage.put(result)

    return {
        "message": message,
        "error": None
    }


@mutation.field("deleteMessage")
@login_required
async def delete_message(_, info, chat_id: str, message_id: int):
    user = info.context["request"].user

    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {"error": "chat not exist"}
    chat = json.loads(chat)

    message = await redis.execute("GET", f"chats/{chat_id}/messages/{str(message_id)}")
    if not message:
        return {"error": "message  not exist"}
    message = json.loads(message)
    if message["author"] != user.slug:
        return {"error": "access denied"}

    await redis.execute("LREM", f"chats/{chat_id}/message_ids", 0, str(message_id))
    await redis.execute("DEL", f"chats/{chat_id}/messages/{str(message_id)}")

    users = chat["users"]
    for user_slug in users:
        await redis.execute("LREM", f"chats/{chat_id}/unread/{user_slug}", 0, str(message_id))

    result = MessageResult("DELETED", message)
    await MessagesStorage.put(result)

    return {}


@mutation.field("markAsRead")
@login_required
async def mark_as_read(_, info, chat_id: str, messages: [int]):
    user = info.context["request"].user

    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {"error": "chat not exist"}

    chat = json.loads(chat)
    users = set(chat["users"])
    if user.slug not in users:
        return {"error": "access denied"}

    for message_id in messages:
        await redis.execute("LREM", f"chats/{chat_id}/unread/{user.slug}", 0, str(message_id))

    return {
        "error": None
    }


@subscription.source("newMessage")
@login_required
async def message_generator(obj, info):
    try:
        user = info.context["request"].user
        user_following_chats = await get_chats_by_user(user.slug)  # chat ids
        tasks = []
        updated = {}
        for chat_id in user_following_chats:
            chat = await redis.execute("GET", f"chats/{chat_id}")
            updated[chat_id] = chat['updatedAt']
        user_following_chats_sorted = sorted(user_following_chats, key=lambda x: updated[x], reverse=True)
        for chat_id in user_following_chats_sorted:
            following_chat = ChatFollowing(chat_id)
            await MessagesStorage.register_chat(following_chat)
            chat_task = following_chat.queue.get()
            tasks.append(chat_task)

        while True:
            msg = await asyncio.gather(*tasks)
            yield msg
    finally:
        await MessagesStorage.remove_chat(following_chat)
