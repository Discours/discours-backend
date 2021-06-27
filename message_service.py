from ariadne import QueryType
from ariadne import MutationType
from ariadne import SubscriptionType
from ariadne import ScalarType
from ariadne import make_executable_schema, load_schema_from_path
from ariadne.asgi import GraphQL

from datetime import datetime

from peewee import *

import asyncio

import auth_utils


type_defs = load_schema_from_path("schema.graphql")

db = SqliteDatabase('discours.db')

class User(Model):
	username = CharField()
	email = CharField()
	createdAt = DateTimeField(default=datetime.now)
	muted = BooleanField(default=False)
	rating = IntegerField(default=0)
	# roles = 
	updatedAt = DateTimeField(default=datetime.now)
	username = CharField()
	userpic = CharField(default="")
	userpicId = CharField(default="")
	wasOnlineAt = DateTimeField(default=datetime.now)
	
	password = CharField()

	class Meta:
		database = db


class Message(Model):
	author = ForeignKeyField(User)
	body = CharField()
	createdAt = DateTimeField(default=datetime.now)
	replyTo = ForeignKeyField('self', null=True)
	updatedAt = DateTimeField(default=datetime.now)

	class Meta:
		database = db


db.connect()
db.create_tables([User, Message])

#only_user = User.create(
#	username = "admin",
#	email = "knst.kotov@gmail.com",
#	password = auth_utils.password_to_hash("12345")
#)
only_user = User.get(User.username == "admin")


all_messages = {}
for message in Message.select():
	all_messages[message.id] = message

new_message_queue = asyncio.Queue()
updated_message_queue = asyncio.Queue()
deleted_message_queue = asyncio.Queue()

datetime_scalar = ScalarType("DateTime")

@datetime_scalar.serializer
def serialize_datetime(value):
	return value.isoformat()

query = QueryType()

@query.field("getMessages")
def resolve_get_messages(_, info, count, page):
	return all_messages.values()


mutation = MutationType()

@mutation.field("signIn")
def resolve_sign_in(_, info, email, password):
	try:
		user = User.get(User.email == email)
	except DoesNotExist as err:
		return {
			"status" : False,
			"error" : "invalid username or password"
		}
		
	if auth_utils.verify_password(password, user.password) :
		return {
			"status" : True,
			"token" : auth_utils.jwt_encode(user)
		}
		
	return {
		"status" : False,
		"error" : "invalid username or password"
	}

@mutation.field("createMessage")
def resolve_create_message(_, info, input):
	request = info.context["request"]
	
	try:
		user_id = auth_utils.authorize(request)
		user = User.get(User.id == user_id)
		
		new_message = Message.create(
			author = user,
			body = input["body"],
			replyTo = input.get("replyTo")
		)
	except Exception as err:
		return {
			"status" : False,
			"message" : err
		}
	
	all_messages[new_message.id] = new_message
	
	new_message_queue.put_nowait(new_message)
	
	return {
		"status" : True,
		"message" : new_message
	}

@mutation.field("updateMessage")
def resolve_update_message(_, info, input):
	request = info.context["request"]
	
	try:
		user_id = auth_utils.authorize(request)
		user = User.get(User.id == user_id)
	except Exception as err:
		return {
			"status" : False,
			"message" : err
		}
		
	message_id = input["id"]
	body = input["body"]
	
	if not message_id in all_messages:
		return {
			"status" : False,
			"error" : "invalid message id"
		}
	
	updated_message = all_messages[message_id]
	
	if updated_message.author != user:
		return {
			"status" : False,
			"error" : "update this message denied"
		}
	
	updated_message.body = body
	#updated_message.updatedAt = datetime.now
	try:
		updated_message.save()
	except Exception as err:
		return {
			"status" : false,
			"message" : err
		}
	
	updated_message_queue.put_nowait(updated_message)
	
	return {
		"status" : True,
		"message" : updated_message
	}

@mutation.field("deleteMessage")
def resolve_delete_message(_, info, messageId):
	if not messageId in all_messages:
		return {
			"status" : False,
			"error" : "invalid message id"
		}
	message = all_messages[messageId]
	
	try:
		message.delete_instance()
	except Exception as err:
		return {
			"status" : false,
			"message" : err
		}
		
	del all_messages[messageId]
	
	deleted_message_queue.put_nowait(message)
	
	return {
		"status" : True
	}

subscription = SubscriptionType()

@subscription.source("messageCreated")
async def new_message_generator(obj, info):
	while True:
		new_message = await new_message_queue.get()
		yield new_message

@subscription.source("messageUpdated")
async def updated_message_generator(obj, info):
	while True:
		message = await updated_message_queue.get()
		yield message

@subscription.source("messageDeleted")
async def deleted_message_generator(obj, info):
	while True:
		message = await deleted_message_queue.get()
		yield new_message

@subscription.field("messageCreated")
@subscription.field("messageUpdated")
@subscription.field("messageDeleted")
def message_resolver(message, info):
	return message

schema = make_executable_schema(type_defs, query, mutation, subscription, datetime_scalar)
app = GraphQL(schema, debug=True)

db.close()
