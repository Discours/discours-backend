from urllib.parse import quote_plus
from datetime import datetime

from graphql.type import GraphQLResolveInfo
from transliterate import translit

from auth.tokenstorage import TokenStorage
from auth.authenticate import login_required
from auth.email import send_auth_email
from auth.identity import Identity, Password
from base.exceptions import (
    InvalidPassword,
    InvalidToken,
    ObjectNotExist,
    OperationNotAllowed,
)
from base.orm import local_session
from base.resolvers import mutation, query
from orm import User, Role
from resolvers.profile import get_user_info
from settings import SESSION_TOKEN_HEADER


@mutation.field("refreshSession")
@login_required
async def get_current_user(_, info):
    user = info.context["request"].user
    user.lastSeen = datetime.now()
    with local_session() as session:
        session.add(user)
        session.commit()
    token = await TokenStorage.create_session(user)
    return {
        "token": token,
        "user": user,
        "info": await get_user_info(user.slug),
    }


@mutation.field("confirmEmail")
async def confirm_email(_, confirm_token):
    """confirm owning email address"""
    user_id = None
    try:
        user_id = await TokenStorage.get(confirm_token)
        with local_session() as session:
            user = session.query(User).where(User.id == user_id).first()
            session_token = TokenStorage.create_session(user)
            user.emailConfirmed = True
            session.add(user)
            session.commit()
        return {"token": session_token, "user": user}
    except InvalidToken as e:
        raise InvalidToken(e.message)
    except Exception as e:
        print(e)  # FIXME: debug only
        return {"error": "email is not confirmed"}


async def confirm_email_handler(request):
    token = request.path_params["token"]
    request.session["token"] = token
    res = confirm_email(None, token)
    return res


@mutation.field("registerUser")
async def register(*_, email: str, password: str = ""):
    """creates new user account"""
    with local_session() as session:
        user = session.query(User).filter(User.email == email).first()
    if user:
        raise OperationNotAllowed("User already exist")
        # return {"error": "user already exist"}

    user_dict = {"email": email}
    username = email.split("@")[0]
    user_dict["username"] = username
    user_dict["slug"] = quote_plus(
        translit(username, "ru", reversed=True).replace(".", "-").lower()
    )
    if password:
        user_dict["password"] = Password.encode(password)
    user = User(**user_dict)
    user.roles.append(Role.default_role)
    with local_session() as session:
        session.add(user)
        session.commit()

    token = await TokenStorage.create_onetime(user)
    await send_auth_email(user, token)

    return {"user": user}


@mutation.field("sendLink")
async def auth_send_link(_, info, email):
    """send link with confirm code to email"""
    with local_session() as session:
        user = session.query(User).filter(User.email == email).first()
    if not user:
        raise ObjectNotExist("User not found")
    token = await TokenStorage.create_onetime(user)
    await send_auth_email(user, token)
    return {}


@query.field("signIn")
async def login(_, info: GraphQLResolveInfo, email: str, password: str = ""):

    with local_session() as session:
        orm_user = session.query(User).filter(User.email == email).first()
        if orm_user is None:
            print(f"[auth] {email}: email not found")
            # return {"error": "email not found"}
            raise ObjectNotExist("User not found")  # contains webserver status

        if not password:
            print(f"[auth] send confirm link to {email}")
            token = await TokenStorage.create_onetime(orm_user)
            await send_auth_email(orm_user, token)
            # FIXME: not an error, warning
            return {"error": "no password, email link was sent"}

        else:
            # sign in using password
            if not orm_user.emailConfirmed:
                # not an error, warns users
                return {"error": "please, confirm email"}
            else:
                try:
                    user = Identity.password(orm_user, password)
                    session_token = await TokenStorage.create_session(user)
                    print(f"[auth] user {email} authorized")
                    return {
                        "token": session_token,
                        "user": user,
                        "info": await get_user_info(user.slug),
                    }
                except InvalidPassword:
                    print(f"[auth] {email}: invalid password")
                    raise InvalidPassword("invalid passoword")  # contains webserver status
                    # return {"error": "invalid password"}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
    token = info.context["request"].headers[SESSION_TOKEN_HEADER]
    status = await TokenStorage.revoke(token)
    return status


@query.field("isEmailUsed")
async def is_email_used(_, info, email):
    with local_session() as session:
        user = session.query(User).filter(User.email == email).first()
    return user is not None
