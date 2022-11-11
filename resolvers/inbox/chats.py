import json
import uuid
from datetime import datetime

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import mutation, query
from resolvers.inbox.messages import load_messages


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
    for member in chat["users"]:
        chats_ids = await redis.execute("GET", f"chats_by_user/{member}")
        if chats_ids:
            chats_ids = list(json.loads(chats_ids))
        else:
            chats_ids = []
        if chat_id not in chats_ids:
            chats_ids.append(chat_id)
        await redis.execute("SET", f"chats_by_user/{member}", json.dumps(chats_ids))


async def get_chats_by_user(slug: str):
    chats = await redis.execute("GET", f"chats_by_user/{slug}")
    if chats:
        chats = list(json.loads(chats))
    return chats or []


async def load_user_chats(slug, offset: int, amount: int):
    """ load :amount chats of :slug user with :offset """
    chats = await get_chats_by_user(slug)[offset:offset + amount]
    if not chats:
        chats = []
    for c in chats:
        c['messages'] = await load_messages(c['id'])
        c['unread'] = await get_unread_counter(c['id'], slug)
    return {
        "chats": chats,
        "error": None
    }


@query.field("loadChats")
@login_required
async def load_chats(_, info):
    user = info.context["request"].user
    return await load_user_chats(user.slug)


@mutation.field("enterChat")
@login_required
async def enter_chat(_, info, chat_id: str):
    ''' enter to public chat with :chat_id '''
    user = info.context["request"].user
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    else:
        chat = dict(json.loads(chat))
        if chat['private']:
            return {
                "error": "cannot enter private chat"
            }
        if user.slug not in chat["users"]:
            chat["users"].append(user.slug)
            await add_user_to_chat(user.slug, chat_id, chat)
            await redis.execute("SET" f"chats/{chat_id}", json.dumps(chat))
        chat['messages'] = await load_messages(chat_id)
        return {
            "chat": chat,
            "error": None
        }


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
