from orm import Message, User
from orm.base import local_session

from resolvers.base import mutation, query, subscription

from auth.authenticate import login_required

import asyncio


class MessageQueue:
	
	new_message = asyncio.Queue()
	updated_message = asyncio.Queue()
	deleted_message = asyncio.Queue()


@mutation.field("createMessage")
@login_required
async def create_message(_, info, body, replyTo = None):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	new_message = Message.create(
		author = user_id,
		body = body,
		replyTo = replyTo
		)
	
	MessageQueue.new_message.put_nowait(new_message)
	
	return {"message" : new_message}

@query.field("getMessages")
@login_required
async def get_messages(_, info, count, page):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		messages = session.query(Message).filter(Message.author == user_id)
	
	return messages

def check_and_get_message(message_id, user_id, session) :
	message = session.query(Message).filter(Message.id == message_id).first()
	
	if not message :
		raise Exception("invalid id")
	
	if message.author != user_id :
		raise Exception("access denied")
	
	return message

@mutation.field("updateMessage")
@login_required
async def update_message(_, info, id, body):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		try:
			message = check_and_get_message(id, user_id, session)
		except Exception as err:
			return {"error" : err}
	
		message.body = body
		session.commit()
	
	MessageQueue.updated_message.put_nowait(message)
	
	return {"message" : message}

@mutation.field("deleteMessage")
@login_required
async def delete_message(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		try:
			message = check_and_get_message(id, user_id, session)
		except Exception as err:
			return {"error" : err}
	
		session.delete(message)
		session.commit()
	
	MessageQueue.deleted_message.put_nowait(message)
	
	return {}


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
