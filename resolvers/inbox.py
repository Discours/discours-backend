import asyncio
import json
import uuid
from datetime import datetime

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import mutation, query, subscription
from services.inbox import ChatFollowing, MessageResult, MessagesStorage


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


async def add_user_to_chat(user_slug: str, chat_id: str, chat=None):
    chats_ids = await redis.execute("GET", f"chats_by_user/{user_slug}")
    if not chat:
        chat = await redis.execute("GET", f"chats/{chat_id}")
        if chat:
            chat = dict(json.loads(chat))
    if chats_ids:
        chats_ids = list(json.loads(chats_ids))
    else:
        chats_ids = []
    if chat_id not in chats_ids:
        chats_ids.append(chat_id)
    await redis.execute("SET", f"chats_by_user/{user_slug}", json.dumps(chats_ids))
    if user_slug not in chat["users"]:
        chat["users"].append(user_slug)
        chat["updatedAt"] = int(datetime.now().timestamp())
    await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
    return chat


async def get_chats_by_user(slug: str):
    chats = await redis.execute("GET", f"chats_by_user/{slug}")
    return chats or []


@mutation.field("inviteChat")
async def invite_to_chat(_, info, invited: str, chat_id: str):
    user = info.context["request"].user
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if user.slug not in chat['users']:
        # TODO: check right to invite here
        chat = await add_user_to_chat(invited, chat_id, chat)
    return {
        "error": None,
        "chat": chat
    }


@mutation.field("updateChat")
@login_required
async def update_chat(_, info, chat_new):
    user = info.context["request"].user

    chat = await redis.execute("GET", f"chats/{chat_new.id}")
    chat.update({
        "title": chat_new.title,
        "description": chat_new.description,
        "updatedAt": int(datetime.now().timestamp()),
    })

    await redis.execute("SET", f"chats/{chat.id}", json.dumps(chat))
    await redis.execute("SET", f"chats/{chat.id}/next_message_id", 0)
    chat = await add_user_to_chat(user.slug, chat.id)

    return {
        "error": None,
        "chat": chat
    }


@mutation.field("createChat")
@login_required
async def create_chat(_, info, title="", members=[]):
    user = info.context["request"].user
    if user.slug not in members:
        members.append(user.slug)
    chat_id = str(uuid.uuid4())
    chat = {
        "title": title,
        "createdAt": int(datetime.now().timestamp()),
        "updatedAt": int(datetime.now().timestamp()),
        "createdBy": user.slug,
        "id": chat_id,
        "users": members,
    }

    await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
    await redis.execute("SET", f"chats/{chat_id}/next_message_id", str(0))
    chat = await add_user_to_chat(user.slug, chat_id)

    return {
        "error": None,
        "chat": chat
    }


async def load_messages(chatId: str, offset: int, amount: int):
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


@query.field("myChats")
@login_required
async def user_chats(_, info):
    user = info.context["request"].user
    chats = await get_chats_by_user(user.slug)
    if not chats:
        chats = []
    for c in chats:
        c['messages'] = await load_messages(c['id'])
        c['unread'] = await get_unread_counter(c['id'], user.slug)
    return {
        "chats": chats,
        "error": None
    }


@mutation.field("enterChat")
@login_required
async def enter_chat(_, info, chat_id: str):
    user = info.context["request"].user
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    else:
        chat = json.loads(chat)
        chat = await add_user_to_chat(user.slug, chat_id, chat)
        chat['messages'] = await load_messages(chat_id)
        return {
            "chat": chat,
            "error": None
        }


@mutation.field("createMessage")
@login_required
async def create_message(_, info, chat_id: str, body: str, replyTo=None):
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


@query.field("loadChat")
@login_required
async def load_chat_messages(_, info, chat_id: str, offset: int = 0, amount: int = 50):
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
