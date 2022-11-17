import json
import uuid
from datetime import datetime

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import mutation, query
from services.auth.users import UserStorage


async def add_user_to_chat(user_slug: str, chat_id: str, chat=None):
    for member in chat["users"]:
        chats_ids = await redis.execute("GET", f"chats_by_user/{member}")
        if chats_ids:
            chats_ids = list(json.loads(chats_ids))
        else:
            chats_ids = []
        if chat_id not in chats_ids:
            chats_ids.append(chat_id)
        await redis.execute("SET", f"chats_by_user/{member}", json.dumps(chats_ids))


@mutation.field("inviteChat")
async def invite_to_chat(_, info, invited: str, chat_id: str):
    ''' invite user with :slug to chat with :chat_id '''
    user = info.context["request"].user
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    chat = dict(json.loads(chat))
    if not chat['private'] and user.slug not in chat['admins']:
        return {
            "error": "only admins can invite to private chat",
            "chat": chat
        }
    else:
        chat["users"].append(invited)
        await add_user_to_chat(user.slug, chat_id, chat)
        await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
        return {
            "error": None,
            "chat": chat
        }


@mutation.field("updateChat")
@login_required
async def update_chat(_, info, chat_new: dict):
    """
    updating chat
    requires info["request"].user.slug to be in chat["admins"]

    :param info: GraphQLInfo with request
    :param chat_new: dict with chat data
    :return: Result { error chat }
    """
    user = info.context["request"].user
    chat_id = chat_new["id"]
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    chat = dict(json.loads(chat))
    if user.slug in chat["admins"]:
        chat.update({
            "title": chat_new.get("title", chat["title"]),
            "description": chat_new.get("description", chat["description"]),
            "updatedAt": int(datetime.now().timestamp()),
            "admins": chat_new.get("admins", chat["admins"]),
            "users": chat_new.get("users", chat["users"])
        })
    await add_user_to_chat(user.slug, chat_id, chat)
    await redis.execute("SET", f"chats/{chat.id}", json.dumps(chat))
    await redis.execute("SET", f"chats/{chat.id}/next_message_id", 0)

    return {
        "error": None,
        "chat": chat
    }


@mutation.field("createChat")
@login_required
async def create_chat(_, info, title="", members=[]):
    user = info.context["request"].user
    chat_id = str(uuid.uuid4())
    if user.slug not in members:
        members.append(user.slug)
    chat = {
        "title": title,
        "createdAt": int(datetime.now().timestamp()),
        "updatedAt": int(datetime.now().timestamp()),
        "createdBy": user.slug,
        "id": chat_id,
        "users": members,
        "admins": [user.slug, ]
    }

    await add_user_to_chat(user.slug, chat_id, chat)
    await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
    await redis.execute("SET", f"chats/{chat_id}/next_message_id", str(0))

    return {
        "error": None,
        "chat": chat
    }


@mutation.field("deleteChat")
@login_required
async def delete_chat(_, info, chat_id: str):
    user = info.context["request"].user
    chat = await redis.execute("GET", f"/chats/{chat_id}")
    if chat:
        chat = dict(json.loads(chat))
        if user.slug in chat['admins']:
            await redis.execute("DEL", f"chats/{chat_id}")
    else:
        return {
            "error": "chat not exist"
        }


@query.field("chatUsersAll")
@login_required
async def get_chat_users_all(_, info):
    chat_users = await UserStorage.get_all_chat_users()
    return chat_users
