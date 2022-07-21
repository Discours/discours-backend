from resolvers_base import mutation, query, subscription

from auth.authenticate import login_required

import asyncio, uuid, json
from datetime import datetime

from redis import redis

class ChatFollowing:
	queue = asyncio.Queue()

	def __init__(self, chat_id):
		self.chat_id = chat_id

class MessagesStorage:
	lock = asyncio.Lock()
	chats = []

	@staticmethod
	async def register_chat(chat):
		async with MessagesStorage.lock:
			MessagesStorage.chats.append(chat)
	
	@staticmethod
	async def remove_chat(chat):
		async with MessagesStorage.lock:
			MessagesStorage.chats.remove(chat)
	
	@staticmethod
	async def put(message_result):
		async with MessagesStorage.lock:
			for chat in MessagesStorage.chats:
				if message_result.message["chatId"] == chat.chat_id:
					chat.queue.put_nowait(message_result)

class MessageResult:
	def __init__(self, status, message):
		self.status = status
		self.message = message

async def get_inbox_counter(user_slug):
	chats = await redis.execute("GET", f"chats_by_user/{user_slug}")
	if not chats:
		return 0

	chats = json.loads(chats)
	unread = 0
	for chat_id in chats:
		n = await redis.execute("LLEN", f"chats/{chat_id}/unread/{user_slug}")
		unread += n

	return unread

async def add_user_to_chat(user_slug, chat_id, chat = None):
	chats = await redis.execute("GET", f"chats_by_user/{user_slug}")
	if not chats:
		chats = set()
	else:
		chats = set(json.loads(chats))
	chats.add(str(chat_id))
	chats = list(chats)
	await redis.execute("SET", f"chats_by_user/{user_slug}", json.dumps(chats))

	if chat:
		users = set(chat["users"])
		users.add(user_slug)
		chat["users"] = list(users)
		await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))

@mutation.field("createChat")
@login_required
async def create_chat(_, info, description):
	user = info.context["request"].user

	chat_id = uuid.uuid4()
	chat = {
		"description" : description,
		"createdAt" : str(datetime.now),
		"createdBy" : user.slug,
		"id" : str(chat_id),
		"users" : [user.slug]
	}

	await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
	await redis.execute("SET", f"chats/{chat_id}/next_message_id", 0)

	await add_user_to_chat(user.slug, chat_id)

	return { "chatId" : chat_id }

async def load_messages(chatId, size, page):
	message_ids = await redis.lrange(f"chats/{chatId}/message_ids",
		size * (page -1), size * page - 1)
	messages = []
	if message_ids:
		message_keys = [f"chats/{chatId}/messages/{id.decode('UTF-8')}" for id in message_ids]
		messages = await redis.mget(*message_keys)
		messages = [json.loads(msg) for msg in messages]
	return messages

@query.field("userChats")
@login_required
async def user_chats(_, info):
	user = info.context["request"].user

	chats = await redis.execute("GET", f"chats_by_user/{user.slug}")
	if not chats:
		chats = list()
	else:
		chats = list(json.loads(chats))

	return {"chats" : chats}

@query.field("enterChat")
@login_required
async def enter_chat(_, info, chatId, size):
	user = info.context["request"].user

	chat = await redis.execute("GET", f"chats/{chatId}")
	if not chat:
		return { "error" : "chat not exist" }
	chat = json.loads(chat)

	messages = await load_messages(chatId, size, 1)

	await add_user_to_chat(user.slug, chatId, chat)

	return { 
		"chat" : chat,
		"messages" : messages 
	}

@mutation.field("createMessage")
@login_required
async def create_message(_, info, chatId, body, replyTo = None):
	user = info.context["request"].user

	chat = await redis.execute("GET", f"chats/{chatId}")
	if not chat:
		return { "error" : "chat not exist" }

	message_id = await redis.execute("GET", f"chats/{chatId}/next_message_id")
	message_id = int(message_id)

	new_message = {
		"chatId" : chatId,
		"id" : message_id,
		"author" : user.slug,
		"body" : body,
		"replyTo" : replyTo,
		"createdAt" : datetime.now().isoformat()
	}

	await redis.execute("SET", f"chats/{chatId}/messages/{message_id}", json.dumps(new_message))
	await redis.execute("LPUSH", f"chats/{chatId}/message_ids", str(message_id))
	await redis.execute("SET", f"chats/{chatId}/next_message_id", str(message_id + 1))

	chat = json.loads(chat)
	users = chat["users"]
	for user_slug in users:
		await redis.execute("LPUSH", f"chats/{chatId}/unread/{user_slug}", str(message_id))

	result = MessageResult("NEW", new_message)
	await MessagesStorage.put(result)

	return {"message" : new_message}

@query.field("getMessages")
@login_required
async def get_messages(_, info, chatId, size, page):
	chat = await redis.execute("GET", f"chats/{chatId}")
	if not chat:
		return { "error" : "chat not exist" }

	messages = await load_messages(chatId, size, page)

	return messages

@mutation.field("updateMessage")
@login_required
async def update_message(_, info, chatId, id, body):
	user = info.context["request"].user

	chat = await redis.execute("GET", f"chats/{chatId}")
	if not chat:
		return { "error" : "chat not exist" }

	message = await redis.execute("GET", f"chats/{chatId}/messages/{id}")
	if not message:
		return { "error" : "message  not exist" }

	message = json.loads(message)
	if message["author"] != user.slug:
		return { "error" : "access denied" }

	message["body"] = body
	message["updatedAt"] = datetime.now().isoformat()

	await redis.execute("SET", f"chats/{chatId}/messages/{id}", json.dumps(message))

	result = MessageResult("UPDATED", message)
	await MessagesStorage.put(result)

	return {"message" : message}

@mutation.field("deleteMessage")
@login_required
async def delete_message(_, info, chatId, id):
	user = info.context["request"].user

	chat = await redis.execute("GET", f"chats/{chatId}")
	if not chat:
		return { "error" : "chat not exist" }

	message = await redis.execute("GET", f"chats/{chatId}/messages/{id}")
	if not message:
		return { "error" : "message  not exist" }
	message = json.loads(message)
	if message["author"] != user.slug:
		return { "error" : "access denied" }

	await redis.execute("LREM", f"chats/{chatId}/message_ids", 0, str(id))
	await redis.execute("DEL", f"chats/{chatId}/messages/{id}")

	chat = json.loads(chat)
	users = chat["users"]
	for user_slug in users:
		await redis.execute("LREM", f"chats/{chatId}/unread/{user_slug}", 0, str(id))

	result = MessageResult("DELETED", message)
	await MessagesStorage.put(result)

	return {}

@mutation.field("markAsRead")
@login_required
async def mark_as_read(_, info, chatId, ids):
	user = info.context["request"].user

	chat = await redis.execute("GET", f"chats/{chatId}")
	if not chat:
		return { "error" : "chat not exist" }

	chat = json.loads(chat)
	users = set(chat["users"])
	if not user.slug in users:
		return { "error" : "access denied" }

	for id in ids:
		await redis.execute("LREM", f"chats/{chatId}/unread/{user.slug}", 0, str(id))

	return {}

@subscription.source("chatUpdated")
async def message_generator(obj, info, chatId):

	#TODO: send AUTH header
	#auth = info.context["request"].auth
	#if not auth.logged_in:
	#	yield {"error" : auth.error_message or "Please login"}

	try:
		following_chat = ChatFollowing(chatId)
		await MessagesStorage.register_chat(following_chat)
		while True:
			msg = await following_chat.queue.get()
			yield msg
	finally:
		await MessagesStorage.remove_chat(following_chat)

@subscription.field("chatUpdated")
def message_resolver(message, info, chatId):
	return message
