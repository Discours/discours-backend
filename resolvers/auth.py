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

@mutation.field("SignUp")
async def register(*_, create: dict = None) -> User:
    create_user = CreateUser(**create)
    create_user.password = Password.encode(create_user.password)
    return User.create(**create_user.dict())


@query.field("SignIn")
async def login(_, info: GraphQLResolveInfo, id: int, password: str) -> str:
    try:
        device = info.context["request"].headers['device']
    except KeyError:
        device = "pc"
    auto_delete = False if device == "mobile" else True
    user = Identity.identity(user_id=id, password=password)
    return await Authorize.authorize(user, device=device, auto_delete=auto_delete)


# TODO: implement some queries, ex. @query.field("isUsernameFree")

@query.field("logout")
@login_required
async def logout(_, info: GraphQLResolveInfo, id: int) -> bool:
    token = info.context["request"].headers[JWT_AUTH_HEADER]
    return await Authorize.revoke(token)


@query.field("getUser")
@login_required
async def get_user(*_, id: int):
    return global_session.query(User).filter(User.id == id).first()


