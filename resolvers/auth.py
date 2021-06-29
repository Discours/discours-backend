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
async def register(*_, input: dict = None) -> User:
    create_user = CreateUser(**input)
    create_user.password = Password.encode(create_user.password)
    return User.create(**create_user.dict())


@query.field("signIn")
async def sign_in(_, info: GraphQLResolveInfo, id: int, password: str):
    try:
        device = info.context["request"].headers['device']
    except KeyError:
        device = "pc"
    auto_delete = False if device == "mobile" else True
    user = Identity.identity(user_id=id, password=password)
    token = await Authorize.authorize(user, device=device, auto_delete=auto_delete)
    return {"status" : True, "token" : token}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
    token = info.context["request"].headers[JWT_AUTH_HEADER]
    status = await Authorize.revoke(token)
    return {"status" : status}


#@query.field("getUser")
#@login_required
async def get_user(*_, id: int):
    return global_session.query(User).filter(User.id == id).first()


