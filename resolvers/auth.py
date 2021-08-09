from graphql import GraphQLResolveInfo
from datetime import datetime, timedelta
from auth.authenticate import login_required
from auth.authorize import Authorize
from auth.identity import Identity
from auth.password import Password
from auth.validations import CreateUser
from orm import User
from orm.base import local_session
from resolvers.base import mutation, query
from exceptions import InvalidPassword

from settings import JWT_AUTH_HEADER

@mutation.field("confirmEmail")
async def confirm(*_, confirm_token):
	auth_token, user = await Authorize.confirm(confirm_token)
	if auth_token:
		user.emailConfirmed = True
		user.save()
		return { "token": auth_token, "user" : user}
	else:
		return { "error": "Email not confirmed"}


@mutation.field("registerUser")
async def register(*_, email: str, password: str = ""):
	inp = { "email": email, "password": password}
	create_user = CreateUser(**inp)
	create_user.username = email.split('@')[0]
	if not password:
		# NOTE: 1 hour confirm_token expire
		confirm_token = Token.encode(create_user, datetime.now() + timedelta(hours = 1) , "email")
		# TODO:	sendAuthEmail(confirm_token)
		# без пароля не возвращаем, а высылаем токен на почту
		# 
		return { "user": user }
	else:
		create_user.password = Password.encode(create_user.password)
		user = User.create(**create_user.dict())
		token = await Authorize.authorize(user)
		return {"user": user, "token": token }


@query.field("signIn")
async def login(_, info: GraphQLResolveInfo, email: str, password: str):
	with local_session() as session:
		orm_user = session.query(User).filter(User.email == email).first()
	if orm_user is None:
		return {"error" : "invalid email"}

	try:
		device = info.context["request"].headers['device']
	except KeyError:
		device = "pc"
	auto_delete = False if device == "mobile" else True # why autodelete with mobile?

	try:
		user = Identity.identity(user_id=orm_user.id, password=password)
	except InvalidPassword:
		return {"error" : "invalid password"}
	
	token = await Authorize.authorize(user, device=device, auto_delete=auto_delete)
	return {"token" : token, "user": user}}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
	token = info.context["request"].headers[JWT_AUTH_HEADER]
	status = await Authorize.revoke(token)
	return True

@query.field("getCurrentUser")
@login_required
async def get_user(_, info):
	auth = info.context["request"].auth
	user_id = auth.user_id
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
	return { "user": user }

@query.field("isEmailFree")
async def is_email_free(_, info, email):
	with local_session() as session:
		user = session.query(User).filter(User.email == email).first()
	return user is None
