from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from starlette.responses import RedirectResponse, JSONResponse
from secrets import token_urlsafe
import time

from auth.tokenstorage import TokenStorage
from auth.orm import Author
from services.db import local_session
from settings import FRONTEND_URL, OAUTH_CLIENTS

oauth = OAuth()

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

    # Генерируем PKCE challenge
    code_verifier = token_urlsafe(32)
    code_challenge = create_s256_code_challenge(code_verifier)

    # Сохраняем code_verifier в сессии
    request.session["code_verifier"] = code_verifier
    request.session["provider"] = provider
    request.session["state"] = token_urlsafe(16)

    redirect_uri = f"{FRONTEND_URL}/oauth/callback"

    try:
        return await client.authorize_redirect(
            request,
            redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=request.session["state"],
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def oauth_callback(request):
    """Обрабатывает callback от OAuth провайдера"""
    try:
        provider = request.session.get("provider")
        if not provider:
            return JSONResponse({"error": "No active OAuth session"}, status_code=400)

        # Проверяем state
        state = request.query_params.get("state")
        if state != request.session.get("state"):
            return JSONResponse({"error": "Invalid state"}, status_code=400)

        client = oauth.create_client(provider)
        if not client:
            return JSONResponse({"error": "Provider not configured"}, status_code=400)

        # Получаем токен с PKCE verifier
        token = await client.authorize_access_token(
            request, code_verifier=request.session.get("code_verifier")
        )

        # Получаем профиль пользователя
        profile = await get_user_profile(provider, client, token)
        if not profile.get("email"):
            return JSONResponse({"error": "Email not provided"}, status_code=400)

        # Создаем или обновляем пользователя
        with local_session() as session:
            author = session.query(Author).filter(Author.email == profile["email"]).first()

            if not author:
                author = Author(
                    email=profile["email"],
                    name=profile["name"],
                    username=profile["name"],
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

        # Очищаем сессию OAuth
        request.session.pop("code_verifier", None)
        request.session.pop("provider", None)
        request.session.pop("state", None)

        # Возвращаем токен через cookie
        response = RedirectResponse(url=f"{FRONTEND_URL}/auth/success")
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
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/error?message={str(e)}")
