import time
from secrets import token_urlsafe
from typing import Any, Optional

import orjson
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from graphql import GraphQLResolveInfo
from starlette.requests import Request
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
    "x": {
        "name": "x",
        "access_token_url": "https://api.twitter.com/2/oauth2/token",
        "authorize_url": "https://twitter.com/i/oauth2/authorize",
        "api_base_url": "https://api.twitter.com/2/",
        "client_kwargs": {"scope": "tweet.read users.read offline.access"},
    },
    "telegram": {
        "name": "telegram",
        "authorize_url": "https://oauth.telegram.org/auth",
        "api_base_url": "https://api.telegram.org/",
        "client_kwargs": {"scope": "user:read"},
    },
    "vk": {
        "name": "vk",
        "access_token_url": "https://oauth.vk.com/access_token",
        "authorize_url": "https://oauth.vk.com/authorize",
        "api_base_url": "https://api.vk.com/method/",
        "client_kwargs": {"scope": "email", "v": "5.131"},
    },
    "yandex": {
        "name": "yandex",
        "access_token_url": "https://oauth.yandex.ru/token",
        "authorize_url": "https://oauth.yandex.ru/authorize",
        "api_base_url": "https://login.yandex.ru/info",
        "client_kwargs": {"scope": "login:email login:info"},
    },
}

# Регистрация провайдеров
for provider, config in PROVIDERS.items():
    if provider in OAUTH_CLIENTS and OAUTH_CLIENTS[provider.upper()]:
        client_config = OAUTH_CLIENTS[provider.upper()]
        if "id" in client_config and "key" in client_config:
            try:
                # Регистрируем провайдеров вручную для избежания проблем типизации
                if provider == "google":
                    oauth.register(
                        name="google",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                    )
                elif provider == "github":
                    oauth.register(
                        name="github",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        access_token_url="https://github.com/login/oauth/access_token",
                        authorize_url="https://github.com/login/oauth/authorize",
                        api_base_url="https://api.github.com/",
                    )
                elif provider == "facebook":
                    oauth.register(
                        name="facebook",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        access_token_url="https://graph.facebook.com/v13.0/oauth/access_token",
                        authorize_url="https://www.facebook.com/v13.0/dialog/oauth",
                        api_base_url="https://graph.facebook.com/",
                    )
                elif provider == "x":
                    oauth.register(
                        name="x",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        access_token_url="https://api.twitter.com/2/oauth2/token",
                        authorize_url="https://twitter.com/i/oauth2/authorize",
                        api_base_url="https://api.twitter.com/2/",
                    )
                elif provider == "telegram":
                    oauth.register(
                        name="telegram",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        authorize_url="https://oauth.telegram.org/auth",
                        api_base_url="https://api.telegram.org/",
                    )
                elif provider == "vk":
                    oauth.register(
                        name="vk",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        access_token_url="https://oauth.vk.com/access_token",
                        authorize_url="https://oauth.vk.com/authorize",
                        api_base_url="https://api.vk.com/method/",
                    )
                elif provider == "yandex":
                    oauth.register(
                        name="yandex",
                        client_id=client_config["id"],
                        client_secret=client_config["key"],
                        access_token_url="https://oauth.yandex.ru/token",
                        authorize_url="https://oauth.yandex.ru/authorize",
                        api_base_url="https://login.yandex.ru/info",
                    )
                logger.info(f"OAuth provider {provider} registered successfully")
            except Exception as e:
                logger.error(f"Failed to register OAuth provider {provider}: {e}")
                continue


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
    if provider == "github":
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
    if provider == "facebook":
        profile = await client.get("me?fields=id,name,email,picture.width(600)", token=token)
        profile_data = profile.json()
        return {
            "id": profile_data["id"],
            "email": profile_data.get("email"),
            "name": profile_data.get("name"),
            "picture": profile_data.get("picture", {}).get("data", {}).get("url"),
        }
    if provider == "x":
        # Twitter/X API v2
        profile = await client.get("users/me?user.fields=id,name,username,profile_image_url", token=token)
        profile_data = profile.json()
        user_data = profile_data.get("data", {})
        return {
            "id": user_data.get("id"),
            "email": None,  # X не предоставляет email через API
            "name": user_data.get("name") or user_data.get("username"),
            "picture": user_data.get("profile_image_url", "").replace("_normal", "_400x400"),
        }
    if provider == "telegram":
        # Telegram OAuth (через Telegram Login Widget)
        # Данные обычно приходят в token параметрах
        return {
            "id": str(token.get("id", "")),
            "email": None,  # Telegram не предоставляет email
            "phone": str(token.get("phone_number", "")),
            "name": token.get("first_name", "") + " " + token.get("last_name", ""),
            "picture": token.get("photo_url"),
        }
    if provider == "vk":
        # VK API
        profile = await client.get("users.get?fields=photo_400_orig,contacts&v=5.131", token=token)
        profile_data = profile.json()
        if profile_data.get("response"):
            user_data = profile_data["response"][0]
            return {
                "id": str(user_data["id"]),
                "email": user_data.get("contacts", {}).get("email"),
                "name": f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                "picture": user_data.get("photo_400_orig"),
            }
    if provider == "yandex":
        # Yandex API
        profile = await client.get("?format=json", token=token)
        profile_data = profile.json()
        return {
            "id": profile_data.get("id"),
            "email": profile_data.get("default_email"),
            "name": profile_data.get("display_name") or profile_data.get("real_name"),
            "picture": f"https://avatars.yandex.net/get-yapic/{profile_data.get('default_avatar_id')}/islands-200"
            if profile_data.get("default_avatar_id")
            else None,
        }
    return {}


async def oauth_login(_: None, _info: GraphQLResolveInfo, provider: str, callback_data: dict[str, Any]) -> JSONResponse:
    """
    Обработка OAuth авторизации

    Args:
        provider: Провайдер OAuth (google, github, etc.)
        callback_data: Данные из callback-а

    Returns:
        dict: Результат авторизации с токеном или ошибкой
    """
    if provider not in PROVIDERS:
        return JSONResponse({"error": "Invalid provider"}, status_code=400)

    client = oauth.create_client(provider)
    if not client:
        return JSONResponse({"error": "Provider not configured"}, status_code=400)

    # Получаем параметры из query string
    state = callback_data.get("state")
    redirect_uri = callback_data.get("redirect_uri", FRONTEND_URL)

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
    oauth_callback_uri = f"{callback_data['base_url']}oauth/{provider}/callback"

    try:
        return await client.authorize_redirect(
            callback_data["request"],
            oauth_callback_uri,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=state,
        )
    except Exception as e:
        logger.error(f"OAuth redirect error for {provider}: {e!s}")
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

        # Для некоторых провайдеров (X, Telegram) email может отсутствовать
        email = profile.get("email")
        if not email:
            # Генерируем временный email на основе провайдера и ID
            email = f"{provider}_{profile.get('id', 'unknown')}@oauth.local"
            logger.info(f"Generated temporary email for {provider} user: {email}")

        # Создаем или обновляем пользователя
        with local_session() as session:
            # Сначала ищем пользователя по OAuth
            author = Author.find_by_oauth(provider, profile["id"], session)

            if author:
                # Пользователь найден по OAuth - обновляем данные
                author.set_oauth_account(provider, profile["id"], email=profile.get("email"))

                # Обновляем основные данные автора если они пустые
                if profile.get("name") and not author.name:
                    author.name = profile["name"]  # type: ignore[assignment]
                if profile.get("picture") and not author.pic:
                    author.pic = profile["picture"]  # type: ignore[assignment]
                author.updated_at = int(time.time())  # type: ignore[assignment]
                author.last_seen = int(time.time())  # type: ignore[assignment]

            else:
                # Ищем пользователя по email если есть настоящий email
                author = None
                if email and email != f"{provider}_{profile.get('id', 'unknown')}@oauth.local":
                    author = session.query(Author).filter(Author.email == email).first()

                if author:
                    # Пользователь найден по email - добавляем OAuth данные
                    author.set_oauth_account(provider, profile["id"], email=profile.get("email"))

                    # Обновляем данные автора если нужно
                    if profile.get("name") and not author.name:
                        author.name = profile["name"]  # type: ignore[assignment]
                    if profile.get("picture") and not author.pic:
                        author.pic = profile["picture"]  # type: ignore[assignment]
                    author.updated_at = int(time.time())  # type: ignore[assignment]
                    author.last_seen = int(time.time())  # type: ignore[assignment]

                else:
                    # Создаем нового пользователя
                    slug = generate_unique_slug(profile["name"] or f"{provider}_{profile.get('id', 'user')}")

                    author = Author(
                        email=email,
                        name=profile["name"] or f"{provider.title()} User",
                        slug=slug,
                        pic=profile.get("picture"),
                        email_verified=True if profile.get("email") else False,
                        created_at=int(time.time()),
                        updated_at=int(time.time()),
                        last_seen=int(time.time()),
                    )
                    session.add(author)
                    session.flush()  # Получаем ID автора

                    # Добавляем OAuth данные для нового пользователя
                    author.set_oauth_account(provider, profile["id"], email=profile.get("email"))

            session.commit()

        # Создаем токен сессии
        session_token = await TokenStorage.create_session(str(author.id))

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
        logger.error(f"OAuth callback error: {e!s}")
        # В случае ошибки редиректим на фронтенд с ошибкой
        fallback_redirect = request.query_params.get("redirect_uri", FRONTEND_URL)
        return RedirectResponse(url=f"{fallback_redirect}?error=oauth_failed&message={e!s}")


async def store_oauth_state(state: str, data: dict) -> None:
    """Сохраняет OAuth состояние в Redis с TTL"""
    key = f"oauth_state:{state}"
    await redis.execute("SETEX", key, OAUTH_STATE_TTL, orjson.dumps(data))


async def get_oauth_state(state: str) -> Optional[dict]:
    """Получает и удаляет OAuth состояние из Redis (one-time use)"""
    key = f"oauth_state:{state}"
    data = await redis.execute("GET", key)
    if data:
        await redis.execute("DEL", key)  # Одноразовое использование
        return orjson.loads(data)
    return None


# HTTP handlers для тестирования
async def oauth_login_http(request: Request) -> JSONResponse | RedirectResponse:
    """HTTP handler для OAuth login"""
    try:
        provider = request.path_params.get("provider")
        if not provider or provider not in PROVIDERS:
            return JSONResponse({"error": "Invalid provider"}, status_code=400)

        client = oauth.create_client(provider)
        if not client:
            return JSONResponse({"error": "Provider not configured"}, status_code=400)

        # Генерируем PKCE challenge
        code_verifier = token_urlsafe(32)
        code_challenge = create_s256_code_challenge(code_verifier)
        state = token_urlsafe(32)

        # Сохраняем состояние в сессии
        request.session["code_verifier"] = code_verifier
        request.session["provider"] = provider
        request.session["state"] = state

        # Сохраняем состояние OAuth в Redis
        oauth_data = {
            "code_verifier": code_verifier,
            "provider": provider,
            "redirect_uri": FRONTEND_URL,
            "created_at": int(time.time()),
        }
        await store_oauth_state(state, oauth_data)

        # URL для callback
        callback_uri = f"{FRONTEND_URL}oauth/{provider}/callback"

        return await client.authorize_redirect(
            request,
            callback_uri,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=state,
        )

    except Exception as e:
        logger.error(f"OAuth login error: {e}")
        return JSONResponse({"error": "OAuth login failed"}, status_code=500)


async def oauth_callback_http(request: Request) -> JSONResponse | RedirectResponse:
    """HTTP handler для OAuth callback"""
    try:
        # Используем GraphQL resolver логику
        provider = request.session.get("provider")
        if not provider:
            return JSONResponse({"error": "No OAuth session found"}, status_code=400)

        state = request.query_params.get("state")
        session_state = request.session.get("state")

        if not state or state != session_state:
            return JSONResponse({"error": "Invalid or expired OAuth state"}, status_code=400)

        oauth_data = await get_oauth_state(state)
        if not oauth_data:
            return JSONResponse({"error": "Invalid or expired OAuth state"}, status_code=400)

        # Используем существующую логику
        client = oauth.create_client(provider)
        token = await client.authorize_access_token(request)

        profile = await get_user_profile(provider, client, token)
        if not profile:
            return JSONResponse({"error": "Failed to get user profile"}, status_code=400)

        # Для некоторых провайдеров (X, Telegram) email может отсутствовать
        email = profile.get("email")
        if not email:
            # Генерируем временный email на основе провайдера и ID
            email = f"{provider}_{profile.get('id', 'unknown')}@oauth.local"

        # Регистрируем/обновляем пользователя
        with local_session() as session:
            # Сначала ищем пользователя по OAuth
            author = Author.find_by_oauth(provider, profile["id"], session)

            if author:
                # Пользователь найден по OAuth - обновляем данные
                author.set_oauth_account(provider, profile["id"], email=profile.get("email"))

                # Обновляем основные данные автора если они пустые
                if profile.get("name") and not author.name:
                    author.name = profile["name"]  # type: ignore[assignment]
                if profile.get("picture") and not author.pic:
                    author.pic = profile["picture"]  # type: ignore[assignment]
                author.updated_at = int(time.time())  # type: ignore[assignment]
                author.last_seen = int(time.time())  # type: ignore[assignment]

            else:
                # Ищем пользователя по email если есть настоящий email
                author = None
                if email and email != f"{provider}_{profile.get('id', 'unknown')}@oauth.local":
                    author = session.query(Author).filter(Author.email == email).first()

                if author:
                    # Пользователь найден по email - добавляем OAuth данные
                    author.set_oauth_account(provider, profile["id"], email=profile.get("email"))

                    # Обновляем данные автора если нужно
                    if profile.get("name") and not author.name:
                        author.name = profile["name"]  # type: ignore[assignment]
                    if profile.get("picture") and not author.pic:
                        author.pic = profile["picture"]  # type: ignore[assignment]
                    author.updated_at = int(time.time())  # type: ignore[assignment]
                    author.last_seen = int(time.time())  # type: ignore[assignment]

                else:
                    # Создаем нового пользователя
                    slug = generate_unique_slug(profile["name"] or f"{provider}_{profile.get('id', 'user')}")

                    author = Author(
                        email=email,
                        name=profile["name"] or f"{provider.title()} User",
                        slug=slug,
                        pic=profile.get("picture"),
                        email_verified=True if profile.get("email") else False,
                        created_at=int(time.time()),
                        updated_at=int(time.time()),
                        last_seen=int(time.time()),
                    )
                    session.add(author)
                    session.flush()  # Получаем ID автора

                    # Добавляем OAuth данные для нового пользователя
                    author.set_oauth_account(provider, profile["id"], email=profile.get("email"))

            session.commit()

            # Создаем токен сессии
            session_token = await TokenStorage.create_session(str(author.id))

            # Очищаем OAuth сессию
            request.session.pop("code_verifier", None)
            request.session.pop("provider", None)
            request.session.pop("state", None)

            # Возвращаем redirect с cookie
            response = RedirectResponse(url="/auth/success", status_code=307)
            response.set_cookie(
                "session_token",
                session_token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=30 * 24 * 60 * 60,  # 30 дней
            )
            return response

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return JSONResponse({"error": "OAuth callback failed"}, status_code=500)
