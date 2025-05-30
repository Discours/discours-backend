import time
from secrets import token_urlsafe

import orjson
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from starlette.responses import JSONResponse, RedirectResponse

from auth.orm import Author
from auth.tokenstorage import TokenStorage
from resolvers.auth import generate_unique_slug
from services.db import local_session
from services.redis import redis
from settings import FRONTEND_URL, OAUTH_CLIENTS
from utils.logger import root_logger as logger

oauth = OAuth()

# OAuth state management через Redis (TTL 10 минут)
OAUTH_STATE_TTL = 600  # 10 минут

# Конфигурация провайдеров
PROVIDERS = {
    "google": {
        "name": "google",
        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
        "client_kwargs": {"scope": "openid email profile", "prompt": "select_account"},
    },
    "github": {
        "name": "github",
        "access_token_url": "https://github.com/login/oauth/access_token",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "api_base_url": "https://api.github.com/",
        "client_kwargs": {"scope": "user:email"},
    },
    "facebook": {
        "name": "facebook",
        "access_token_url": "https://graph.facebook.com/v13.0/oauth/access_token",
        "authorize_url": "https://www.facebook.com/v13.0/dialog/oauth",
        "api_base_url": "https://graph.facebook.com/",
        "client_kwargs": {"scope": "public_profile email"},
    },
}

# Регистрация провайдеров
for provider, config in PROVIDERS.items():
    if provider in OAUTH_CLIENTS:
        oauth.register(
            name=config["name"],
            client_id=OAUTH_CLIENTS[provider.upper()]["id"],
            client_secret=OAUTH_CLIENTS[provider.upper()]["key"],
            **config,
        )


async def get_user_profile(provider: str, client, token) -> dict:
    """Получает профиль пользователя от провайдера OAuth"""
    if provider == "google":
        userinfo = token.get("userinfo", {})
        return {
            "id": userinfo.get("sub"),
            "email": userinfo.get("email"),
            "name": userinfo.get("name"),
            "picture": userinfo.get("picture", "").replace("=s96", "=s600"),
        }
    elif provider == "github":
        profile = await client.get("user", token=token)
        profile_data = profile.json()
        emails = await client.get("user/emails", token=token)
        emails_data = emails.json()
        primary_email = next((email["email"] for email in emails_data if email["primary"]), None)
        return {
            "id": str(profile_data["id"]),
            "email": primary_email or profile_data.get("email"),
            "name": profile_data.get("name") or profile_data.get("login"),
            "picture": profile_data.get("avatar_url"),
        }
    elif provider == "facebook":
        profile = await client.get("me?fields=id,name,email,picture.width(600)", token=token)
        profile_data = profile.json()
        return {
            "id": profile_data["id"],
            "email": profile_data.get("email"),
            "name": profile_data.get("name"),
            "picture": profile_data.get("picture", {}).get("data", {}).get("url"),
        }
    return {}


async def oauth_login(request):
    """Начинает процесс OAuth авторизации"""
    provider = request.path_params["provider"]
    if provider not in PROVIDERS:
        return JSONResponse({"error": "Invalid provider"}, status_code=400)

    client = oauth.create_client(provider)
    if not client:
        return JSONResponse({"error": "Provider not configured"}, status_code=400)

    # Получаем параметры из query string
    state = request.query_params.get("state")
    redirect_uri = request.query_params.get("redirect_uri", FRONTEND_URL)

    if not state:
        return JSONResponse({"error": "State parameter is required"}, status_code=400)

    # Генерируем PKCE challenge
    code_verifier = token_urlsafe(32)
    code_challenge = create_s256_code_challenge(code_verifier)

    # Сохраняем состояние OAuth в Redis
    oauth_data = {
        "code_verifier": code_verifier,
        "provider": provider,
        "redirect_uri": redirect_uri,
        "created_at": int(time.time()),
    }
    await store_oauth_state(state, oauth_data)

    # Используем URL из фронтенда для callback
    oauth_callback_uri = f"{request.base_url}oauth/{provider}/callback"

    try:
        return await client.authorize_redirect(
            request,
            oauth_callback_uri,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=state,
        )
    except Exception as e:
        logger.error(f"OAuth redirect error for {provider}: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def oauth_callback(request):
    """Обрабатывает callback от OAuth провайдера"""
    try:
        # Получаем state из query параметров
        state = request.query_params.get("state")
        if not state:
            return JSONResponse({"error": "State parameter missing"}, status_code=400)

        # Получаем сохраненные данные OAuth из Redis
        oauth_data = await get_oauth_state(state)
        if not oauth_data:
            return JSONResponse({"error": "Invalid or expired OAuth state"}, status_code=400)

        provider = oauth_data.get("provider")
        code_verifier = oauth_data.get("code_verifier")
        stored_redirect_uri = oauth_data.get("redirect_uri", FRONTEND_URL)

        if not provider:
            return JSONResponse({"error": "No active OAuth session"}, status_code=400)

        client = oauth.create_client(provider)
        if not client:
            return JSONResponse({"error": "Provider not configured"}, status_code=400)

        # Получаем токен с PKCE verifier
        token = await client.authorize_access_token(request, code_verifier=code_verifier)

        # Получаем профиль пользователя
        profile = await get_user_profile(provider, client, token)
        if not profile.get("email"):
            return JSONResponse({"error": "Email not provided"}, status_code=400)

        # Создаем или обновляем пользователя
        with local_session() as session:
            author = session.query(Author).filter(Author.email == profile["email"]).first()

            if not author:
                # Генерируем slug из имени или email
                slug = generate_unique_slug(profile["name"] or profile["email"].split("@")[0])

                author = Author(
                    email=profile["email"],
                    name=profile["name"],
                    slug=slug,
                    pic=profile.get("picture"),
                    oauth=f"{provider}:{profile['id']}",
                    email_verified=True,
                    created_at=int(time.time()),
                    updated_at=int(time.time()),
                    last_seen=int(time.time()),
                )
                session.add(author)
            else:
                author.name = profile["name"]
                author.pic = profile.get("picture") or author.pic
                author.oauth = f"{provider}:{profile['id']}"
                author.email_verified = True
                author.updated_at = int(time.time())
                author.last_seen = int(time.time())

            session.commit()

        # Создаем сессию
        session_token = await TokenStorage.create_session(author)

        # Формируем URL для редиректа с токеном
        redirect_url = f"{stored_redirect_uri}?state={state}&access_token={session_token}"
        response = RedirectResponse(url=redirect_url)
        response.set_cookie(
            "session_token",
            session_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=30 * 24 * 60 * 60,  # 30 days
        )
        return response

    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        # В случае ошибки редиректим на фронтенд с ошибкой
        fallback_redirect = request.query_params.get("redirect_uri", FRONTEND_URL)
        return RedirectResponse(url=f"{fallback_redirect}?error=oauth_failed&message={str(e)}")


async def store_oauth_state(state: str, data: dict) -> None:
    """Сохраняет OAuth состояние в Redis с TTL"""
    key = f"oauth_state:{state}"
    await redis.execute("SETEX", key, OAUTH_STATE_TTL, orjson.dumps(data))


async def get_oauth_state(state: str) -> dict:
    """Получает и удаляет OAuth состояние из Redis (one-time use)"""
    key = f"oauth_state:{state}"
    data = await redis.execute("GET", key)
    if data:
        await redis.execute("DEL", key)  # Одноразовое использование
        return orjson.loads(data)
    return None
