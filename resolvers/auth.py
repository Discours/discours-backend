# -*- coding: utf-8 -*-

from datetime import datetime, timezone
from urllib.parse import quote_plus

from graphql.type import GraphQLResolveInfo
from starlette.responses import RedirectResponse
from transliterate import translit

from auth.authenticate import login_required
from auth.email import send_auth_email
from auth.identity import Identity, Password
from auth.jwtcodec import JWTCodec
from auth.tokenstorage import TokenStorage
from base.exceptions import (BaseHttpException, InvalidPassword, InvalidToken,
                             ObjectNotExist, Unauthorized)
from base.orm import local_session
from base.resolvers import mutation, query
from orm import Role, User
from resolvers.zine.profile import user_subscriptions
from settings import SESSION_TOKEN_HEADER, FRONTEND_URL


@mutation.field("getSession")
@login_required
async def get_current_user(_, info):
    user = info.context["request"].user
    token = info.context["request"].headers.get("Authorization")
    if user and token:
        user.lastSeen = datetime.now(tz=timezone.utc)
        with local_session() as session:
            session.add(user)
            session.commit()
            return {
                "token": token,
                "user": user,
                "news": await user_subscriptions(user.slug),
            }
    else:
        raise Unauthorized("No session token present in request, try to login")


@mutation.field("confirmEmail")
async def confirm_email(_, info, token):
    """confirm owning email address"""
    try:
        print('[resolvers.auth] confirm email by token')
        payload = JWTCodec.decode(token)
        user_id = payload.user_id
        await TokenStorage.get(f"{user_id}-{token}")
        with local_session() as session:
            user = session.query(User).where(User.id == user_id).first()
            session_token = await TokenStorage.create_session(user)
            user.emailConfirmed = True
            user.lastSeen = datetime.now(tz=timezone.utc)
            session.add(user)
            session.commit()
            return {
                "token": session_token,
                "user": user,
                "news": await user_subscriptions(user.slug)
            }
    except InvalidToken as e:
        raise InvalidToken(e.message)
    except Exception as e:
        print(e)  # FIXME: debug only
        return {"error": "email is not confirmed"}


async def confirm_email_handler(request):
    token = request.path_params["token"]  # one time
    request.session["token"] = token
    res = await confirm_email(None, {}, token)
    print('[resolvers.auth] confirm_email request: %r' % request)
    if "error" in res:
        raise BaseHttpException(res['error'])
    else:
        response = RedirectResponse(url=FRONTEND_URL)
        response.set_cookie("token", res["token"])  # session token
        return response


def create_user(user_dict):
    user = User(**user_dict)
    with local_session() as session:
        user.roles.append(session.query(Role).first())
        session.add(user)
        session.commit()
    return user


def generate_unique_slug(src):
    print('[resolvers.auth] generating slug from: ' + src)
    slug = translit(src, "ru", reversed=True).replace(".", "-").lower()
    if slug != src:
        print('[resolvers.auth] translited name: ' + slug)
    c = 1
    with local_session() as session:
        user = session.query(User).where(User.slug == slug).first()
        while user:
            user = session.query(User).where(User.slug == slug).first()
            slug = slug + '-' + str(c)
            c += 1
        if not user:
            unique_slug = slug
            print('[resolvers.auth] ' + unique_slug)
            return quote_plus(unique_slug.replace('\'', '')).replace('+', '-')


@mutation.field("registerUser")
async def register_by_email(_, _info, email: str, password: str = "", name: str = ""):
    """creates new user account"""
    with local_session() as session:
        user = session.query(User).filter(User.email == email).first()
    if user:
        raise Unauthorized("User already exist")
    else:
        slug = generate_unique_slug(name)
        user = session.query(User).where(User.slug == slug).first()
        if user:
            slug = generate_unique_slug(email.split('@')[0])
        user_dict = {
            "email": email,
            "username": email,  # will be used to store phone number or some messenger network id
            "name": name,
            "slug": slug
        }
        if password:
            user_dict["password"] = Password.encode(password)
        user = create_user(user_dict)
        user = await auth_send_link(_, _info, email)
        return {"user": user}


@mutation.field("sendLink")
async def auth_send_link(_, _info, email, lang="ru", template="email_confirmation"):
    """send link with confirm code to email"""
    with local_session() as session:
        user = session.query(User).filter(User.email == email).first()
        if not user:
            raise ObjectNotExist("User not found")
        else:
            token = await TokenStorage.create_onetime(user)
            await send_auth_email(user, token, lang, template)
            return user


@query.field("signIn")
async def login(_, info, email: str, password: str = "", lang: str = "ru"):
    with local_session() as session:
        orm_user = session.query(User).filter(User.email == email).first()
        if orm_user is None:
            print(f"[auth] {email}: email not found")
            # return {"error": "email not found"}
            raise ObjectNotExist("User not found")  # contains webserver status

        if not password:
            print(f"[auth] send confirm link to {email}")
            token = await TokenStorage.create_onetime(orm_user)
            await send_auth_email(orm_user, token, lang)
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
                        "news": await user_subscriptions(user.slug),
                    }
                except InvalidPassword:
                    print(f"[auth] {email}: invalid password")
                    raise InvalidPassword("invalid password")  # contains webserver status
                    # return {"error": "invalid password"}


@query.field("signOut")
@login_required
async def sign_out(_, info: GraphQLResolveInfo):
    token = info.context["request"].headers.get(SESSION_TOKEN_HEADER, "")
    status = await TokenStorage.revoke(token)
    return status


@query.field("isEmailUsed")
async def is_email_used(_, _info, email):
    with local_session() as session:
        user = session.query(User).filter(User.email == email).first()
    return user is not None
