from graphql import GraphQLResolveInfo
from datetime import datetime, timedelta
from transliterate import translit
from urllib.parse import quote_plus

from auth.authenticate import login_required, ResetPassword
from auth.authorize import Authorize
from auth.identity import Identity
from auth.password import Password
from auth.email import send_confirm_email, send_auth_email, send_reset_password_email
from orm import User, UserStorage, Role, UserRole
from orm.base import local_session
from resolvers.base import mutation, query
from resolvers.profile import get_user_info
from exceptions import InvalidPassword, InvalidToken

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
	if password:
		user_dict["password"] = Password.encode(password)
	user = User(**user_dict)
	user.roles.append(Role.default_role)
	with local_session() as session:
		session.add(user)
		session.commit()

	await send_confirm_email(user)

	return { "user": user }

@mutation.field("requestPasswordUpdate")
async def request_password_update(_, info, email):
	with local_session() as session:
		user = session.query(User).filter(User.email == email).first()
	if not user:
		return {"error" : "user not exist"}

	await send_reset_password_email(user)

	return {}

@mutation.field("updatePassword")
async def update_password(_, info, password, token):
	try:
		user_id = await ResetPassword.verify(token)
	except InvalidToken as e:
		return {"error" : e.message}

	with local_session() as session:
		user = session.query(User).filter_by(id = user_id).first()
		if not user:
			return {"error" : "user not exist"}
		user.password = Password.encode(password)
		session.commit()

	return {}

@query.field("signIn")
async def login(_, info: GraphQLResolveInfo, email: str, password: str = ""):
	with local_session() as session:
		orm_user = session.query(User).filter(User.email == email).first()
	if orm_user is None:
		print(f"signIn {email}: invalid email")
		return {"error" : "invalid email"}

	if not password:
		print(f"signIn {email}: send auth email")
		await send_auth_email(orm_user)
		return {}

	if not orm_user.emailConfirmed:
		return {"error" : "email not confirmed"}

	try:
		device = info.context["request"].headers['device']
	except KeyError:
		device = "pc"
	auto_delete = False if device == "mobile" else True # why autodelete with mobile?

	try:
		user = Identity.identity(orm_user, password)
	except InvalidPassword:
		print(f"signIn {email}: invalid password")
		return {"error" : "invalid password"}
	
	token = await Authorize.authorize(user, device=device, auto_delete=auto_delete)
	print(f"signIn {email}: OK")

	return {
		"token" : token,
		"user": orm_user,
		"info": await get_user_info(orm_user.slug)
	}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
	token = info.context["request"].headers[JWT_AUTH_HEADER]
	status = await Authorize.revoke(token)
	return True

@query.field("isEmailUsed")
async def is_email_used(_, info, email):
	with local_session() as session:
		user = session.query(User).filter(User.email == email).first()
	return not user is None
