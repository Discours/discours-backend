from graphql import GraphQLResolveInfo
from datetime import datetime, timedelta
from transliterate import translit
from urllib.parse import quote_plus

from auth.authenticate import login_required
from auth.authorize import Authorize
from auth.identity import Identity
from auth.password import Password
from auth.email import send_confirm_email, send_auth_email
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
	with local_session() as session:
		user = session.query(User).filter(User.email == email).first()
	if user:
		return {"error" : "user already exist"}

	user_dict = { "email": email }
	username = email.split('@')[0]
	user_dict["username"] = username
	user_dict["slug"] = quote_plus(translit(username, 'ru', reversed=True).replace('.', '-').lower())
	if not password:
		user = User.create(**user_dict)
		await send_confirm_email(user)
		UserStorage.add_user(user)
		return { "user": user }

	user_dict["password"] = Password.encode(password)
	user = User.create(**user_dict)
	token = await Authorize.authorize(user)
	UserStorage.add_user(user)
	return {"user": user, "token": token }


@query.field("signIn")
async def login(_, info: GraphQLResolveInfo, email: str, password: str = ""):
	with local_session() as session:
		orm_user = session.query(User).filter(User.email == email).first()
	if orm_user is None:
		return {"error" : "invalid email"}

	if not password:
		await send_auth_email(orm_user)
		return {}

	try:
		device = info.context["request"].headers['device']
	except KeyError:
		device = "pc"
	auto_delete = False if device == "mobile" else True # why autodelete with mobile?

	try:
		user = Identity.identity(orm_user, password)
	except InvalidPassword:
		return {"error" : "invalid password"}
	
	token = await Authorize.authorize(user, device=device, auto_delete=auto_delete)
	return {"token" : token, "user": orm_user}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
	token = info.context["request"].headers[JWT_AUTH_HEADER]
	status = await Authorize.revoke(token)
	return True

@query.field("isEmailFree")
async def is_email_free(_, info, email):
	with local_session() as session:
		user = session.query(User).filter(User.email == email).first()
	return user is None
