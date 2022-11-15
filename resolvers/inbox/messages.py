import asyncio
import json
from datetime import datetime

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import mutation, subscription
from services.inbox import ChatFollowing, MessageResult, MessagesStorage


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
        user_following_chats = await redis.execute("GET", f"chats_by_user/{user.slug}")
        if user_following_chats:
            user_following_chats = list(json.loads(user_following_chats))  # chat ids
        else:
            user_following_chats = []
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
