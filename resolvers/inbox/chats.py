import json
import uuid
from datetime import datetime, timezone

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.redis import redis
from base.resolvers import mutation
from validations.inbox import Chat


@mutation.field("updateChat")
@login_required
async def update_chat(_, info, chat_new: Chat):
    """
    updating chat
    requires info["request"].user.slug to be in chat["admins"]

    :param info: GraphQLInfo with request
    :param chat_new: dict with chat data
    :return: Result { error chat }
    """
    auth: AuthCredentials = info.context["request"].auth
    chat_id = chat_new["id"]
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    chat = dict(json.loads(chat))

    # TODO
    if auth.user_id in chat["admins"]:
        chat.update({
            "title": chat_new.get("title", chat["title"]),
            "description": chat_new.get("description", chat["description"]),
            "updatedAt": int(datetime.now(tz=timezone.utc).timestamp()),
            "admins": chat_new.get("admins", chat.get("admins") or []),
            "users": chat_new.get("users", chat["users"])
        })
    await redis.execute("SET", f"chats/{chat.id}", json.dumps(chat))
    await redis.execute("COMMIT")

    return {
        "error": None,
        "chat": chat
    }


@mutation.field("createChat")
@login_required
async def create_chat(_, info, title="", members=[]):
    auth: AuthCredentials = info.context["request"].auth
    chat = {}
    print('create_chat members: %r' % members)
    if auth.user_id not in members:
        members.append(int(auth.user_id))

    # reuse chat craeted before if exists
    if len(members) == 2 and title == "":
        chat = None
        print(members)
        chatset1 = await redis.execute("SMEMBERS", f"chats_by_user/{members[0]}")
        if not chatset1:
            chatset1 = set([])
        print(chatset1)
        chatset2 = await redis.execute("SMEMBERS", f"chats_by_user/{members[1]}")
        if not chatset2:
            chatset2 = set([])
        print(chatset2)
        chatset = chatset1.intersection(chatset2)
        print(chatset)
        for c in chatset:
            chat = await redis.execute("GET", f"chats/{c.decode('utf-8')}")
            if chat:
                chat = json.loads(chat)
                if chat['title'] == "":
                    print('[inbox] createChat found old chat')
                    print(chat)
                    break
        if chat:
            return {
                "chat": chat,
                "error": "existed"
            }

    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "users": members,
        "title": title,
        "createdBy": auth.user_id,
        "createdAt": int(datetime.now(tz=timezone.utc).timestamp()),
        "updatedAt": int(datetime.now(tz=timezone.utc).timestamp()),
        "admins": members if (len(members) == 2 and title == "") else []
    }

    for m in members:
        await redis.execute("SADD", f"chats_by_user/{m}", chat_id)
    await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
    await redis.execute("SET", f"chats/{chat_id}/next_message_id", str(0))
    await redis.execute("COMMIT")
    return {
        "error": None,
        "chat": chat
    }


@mutation.field("deleteChat")
@login_required
async def delete_chat(_, info, chat_id: str):
    auth: AuthCredentials = info.context["request"].auth

    chat = await redis.execute("GET", f"/chats/{chat_id}")
    if chat:
        chat = dict(json.loads(chat))
        if auth.user_id in chat['admins']:
            await redis.execute("DEL", f"chats/{chat_id}")
            await redis.execute("SREM", "chats_by_user/" + str(auth.user_id), chat_id)
            await redis.execute("COMMIT")
    else:
        return {
            "error": "chat not exist"
        }
