from graphql import GraphQLResolveInfo

from auth.authenticate import login_required
from auth.authorize import Authorize
from auth.identity import Identity
from auth.password import Password
from auth.validations import CreateUser
from orm import User
from orm.base import global_session
from resolvers.base import mutation, query

from settings import JWT_AUTH_HEADER

@mutation.field("registerUser")
async def register(*_, email: str, password: str) -> User:
	inp = { "email": email, "password": password}
	create_user = CreateUser(**inp)
	create_user.password = Password.encode(create_user.password)
	create_user.username = email.split('@')[0]
	user = User.create(**create_user.dict())
	# if not password: # TODO: send confirmation email
	token = await Authorize.authorize(user)
	return {"status": True, "user": user, "token": token }


@query.field("signIn")
async def sign_in(_, info: GraphQLResolveInfo, email: str, password: str):
	orm_user = global_session.query(User).filter(User.email == email).first()
	if orm_user is None:
		return {"status" : False, "error" : "invalid email"}

	try:
		device = info.context["request"].headers['device']
	except KeyError:
		device = "pc"
	auto_delete = False if device == "mobile" else True # why autodelete with mobile?
	user = Identity.identity(user_id=orm_user.id, password=password)
	token = await Authorize.authorize(user, device=device, auto_delete=auto_delete)
	return {"status" : True, "token" : token, "user": user}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
	token = info.context["request"].headers[JWT_AUTH_HEADER]
	status = await Authorize.revoke(token)
	return {"status" : status}


@query.field("getCurrentUser")
@login_required
async def get_user(_, info):
	auth = info.context["request"].auth
	user_id = auth.user_id
	user = global_session.query(User).filter(User.id == user_id).first()
	return { "status": True, "user": user }

@query.field("isEmailFree")
async def is_email_free(_, info, email):
	user = global_session.query(User).filter(User.email == email).first()
	return { "status": user is None }


