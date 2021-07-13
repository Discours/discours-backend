from orm import Message, User
from orm.base import global_session

from resolvers.base import mutation, query, subscription

from auth.authenticate import login_required

import asyncio


class MessageQueue:
	
	new_message = asyncio.Queue()
	updated_message = asyncio.Queue()
	deleted_message = asyncio.Queue()


@mutation.field("createMessage")
@login_required
async def create_message(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	new_message = Message.create(
		author = user_id,
		body = input["body"],
		replyTo = input.get("replyTo")
		)
	
	MessageQueue.new_message.put_nowait(new_message)
	
	return {
		"status": True,
		"message" : new_message
	}

@query.field("getMessages")
@login_required
async def get_messages(_, info, count, page):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	messages = global_session.query(Message).filter(Message.author == user_id)
	
	return messages

def check_and_get_message(message_id, user_id) :
	message = global_session.query(Message).filter(Message.id == message_id).first()
	
	if not message :
		raise Exception("invalid id")
	
	if message.author != user_id :
		raise Exception("access denied")
	
	return message

@mutation.field("updateMessage")
@login_required
async def update_message(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id
	message_id = input["id"]
	
	try:
		message = check_and_get_message(message_id, user_id)
	except Exception as err:
		return {
			"status" : False,
			"error" : err
		}
	
	message.body = input["body"]
	global_session.commit()
	
	MessageQueue.updated_message.put_nowait(message)
	
	return {
		"status" : True,
		"message" : message
	}

@mutation.field("deleteMessage")
@login_required
async def delete_message(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	try:
		message = check_and_get_message(id, user_id)
	except Exception as err:
		return {
			"status" : False,
			"error" : err
		}
	
	global_session.delete(message)
	global_session.commit()
	
	MessageQueue.deleted_message.put_nowait(message)
	
	return {
		"status" : True
	}


@subscription.source("messageCreated")
async def new_message_generator(obj, info):
	while True:
		new_message = await MessageQueue.new_message.get()
		yield new_message

@subscription.source("messageUpdated")
async def updated_message_generator(obj, info):
	while True:
		message = await MessageQueue.updated_message.get()
		yield message

@subscription.source("messageDeleted")
async def deleted_message_generator(obj, info):
	while True:
		message = await MessageQueue.deleted_message.get()
		yield new_message

@subscription.field("messageCreated")
@subscription.field("messageUpdated")
@subscription.field("messageDeleted")
def message_resolver(message, info):
	return message
