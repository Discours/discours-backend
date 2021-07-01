from orm import Message, User
from orm.base import global_session

from resolvers.base import mutation, query

from auth.authenticate import login_required

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
	
	return {
		"status" : True
	}
