import time
from secrets import token_urlsafe
from typing import Any, Callable, Optional

import orjson
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from graphql import GraphQLResolveInfo
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from auth.orm import Author
from auth.tokens.storage import TokenStorage
from resolvers.auth import generate_unique_slug
from services.db import local_session
from services.redis import redis
from settings import (
    FRONTEND_URL,
    OAUTH_CLIENTS,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
)
from utils.logger import root_logger as logger

# Type для dependency injection сессии
SessionFactory = Callable[[], Session]


class SessionManager:
    """Менеджер сессий для dependency injection с поддержкой тестирования"""

    def __init__(self) -> None:
        self._factory: SessionFactory = local_session

    def set_factory(self, factory: SessionFactory) -> None:
        """Устанавливает фабрику сессий для dependency injection"""
        self._factory = factory

    def get_session(self) -> Session:
        """Получает сессию БД через dependency injection"""
        return self._factory()


# Глобальный менеджер сессий
session_manager = SessionManager()


def set_session_factory(factory: SessionFactory) -> None:
    """
    Устанавливает фабрику сессий для dependency injection.
    Используется в тестах для подмены реальной БД на тестовую.
    """
    session_manager.set_factory(factory)


def get_session() -> Session:
    """
    Получает сессию БД через dependency injection.
    Возвращает сессию которую нужно явно закрывать после использования.

    Внимание: не забывайте закрывать сессию после использования!
    Рекомендуется использовать try/finally блок.
    """
    return session_manager.get_session()


oauth = OAuth()

# OAuth state management через Redis (TTL 10 минут)
OAUTH_STATE_TTL = 600  # 10 минут

# Конфигурация провайдеров для регистрации
PROVIDER_CONFIGS = {
    "google": {
        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
    },
    "github": {
        "access_token_url": "https://github.com/login/oauth/access_token",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "api_base_url": "https://api.github.com/",
    },
    "facebook": {
        "access_token_url": "https://graph.facebook.com/v13.0/oauth/access_token",
        "authorize_url": "https://www.facebook.com/v13.0/dialog/oauth",
        "api_base_url": "https://graph.facebook.com/",
    },
    "x": {
        "access_token_url": "https://api.twitter.com/2/oauth2/token",
        "authorize_url": "https://twitter.com/i/oauth2/authorize",
        "api_base_url": "https://api.twitter.com/2/",
    },
    "telegram": {
        "authorize_url": "https://oauth.telegram.org/auth",
        "api_base_url": "https://api.telegram.org/",
    },
    "vk": {
        "access_token_url": "https://oauth.vk.com/access_token",
        "authorize_url": "https://oauth.vk.com/authorize",
        "api_base_url": "https://api.vk.com/method/",
    },
    "yandex": {
        "access_token_url": "https://oauth.yandex.ru/token",
        "authorize_url": "https://oauth.yandex.ru/authorize",
        "api_base_url": "https://login.yandex.ru/info",
    },
}

# Константы для генерации временного email
TEMP_EMAIL_SUFFIX = "@oauth.local"


def _generate_temp_email(provider: str, user_id: str) -> str:
    """Генерирует временный email для OAuth провайдеров без email"""
    return f"{provider}_{user_id}@oauth.local"


def _register_oauth_provider(provider: str, client_config: dict) -> None:
    """Регистрирует OAuth провайдер в зависимости от его типа"""
    try:
        provider_config = PROVIDER_CONFIGS.get(provider, {})
        if not provider_config:
            logger.warning(f"Unknown OAuth provider: {provider}")
            return

        # Базовые параметры для всех провайдеров
        register_params = {
            "name": provider,
            "client_id": client_config["id"],
            "client_secret": client_config["key"],
            **provider_config,
        }

        oauth.register(**register_params)
        logger.info(f"OAuth provider {provider} registered successfully")
    except Exception as e:
        logger.error(f"Failed to register OAuth provider {provider}: {e}")


for provider in PROVIDER_CONFIGS:
    if provider in OAUTH_CLIENTS and OAUTH_CLIENTS[provider.upper()]:
        client_config = OAUTH_CLIENTS[provider.upper()]
        if "id" in client_config and "key" in client_config:
            _register_oauth_provider(provider, client_config)


# Провайдеры со специальной обработкой данных
PROVIDER_HANDLERS = {
    "google": lambda token, _: {
        "id": token.get("userinfo", {}).get("sub"),
        "email": token.get("userinfo", {}).get("email"),
        "name": token.get("userinfo", {}).get("name"),
        "picture": token.get("userinfo", {}).get("picture", "").replace("=s96", "=s600"),
    },
    "telegram": lambda token, _: {
        "id": str(token.get("id", "")),
        "email": None,
        "phone": str(token.get("phone_number", "")),
        "name": token.get("first_name", "") + " " + token.get("last_name", ""),
        "picture": token.get("photo_url"),
    },
    "x": lambda _, profile_data: {
        "id": profile_data.get("data", {}).get("id"),
        "email": None,
        "name": profile_data.get("data", {}).get("name") or profile_data.get("data", {}).get("username"),
        "picture": profile_data.get("data", {}).get("profile_image_url", "").replace("_normal", "_400x400"),
    },
}


async def _fetch_github_profile(client: Any, token: Any) -> dict:
    """Получает профиль из GitHub API"""
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


async def _fetch_facebook_profile(client: Any, token: Any) -> dict:
    """Получает профиль из Facebook API"""
    profile = await client.get("me?fields=id,name,email,picture.width(600)", token=token)
    profile_data = profile.json()
    return {
        "id": profile_data["id"],
        "email": profile_data.get("email"),
        "name": profile_data.get("name"),
        "picture": profile_data.get("picture", {}).get("data", {}).get("url"),
    }


async def _fetch_x_profile(client: Any, token: Any) -> dict:
    """Получает профиль из X (Twitter) API"""
    profile = await client.get("authors/me?user.fields=id,name,username,profile_image_url", token=token)
    profile_data = profile.json()
    return PROVIDER_HANDLERS["x"](token, profile_data)


async def _fetch_vk_profile(client: Any, token: Any) -> dict:
    """Получает профиль из VK API"""
    profile = await client.get("authors.get?fields=photo_400_orig,contacts&v=5.131", token=token)
    profile_data = profile.json()
    if profile_data.get("response"):
        user_data = profile_data["response"][0]
        return {
            "id": str(user_data["id"]),
            "email": user_data.get("contacts", {}).get("email"),
            "name": f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
            "picture": user_data.get("photo_400_orig"),
        }
    return {}


async def _fetch_yandex_profile(client: Any, token: Any) -> dict:
    """Получает профиль из Yandex API"""
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


async def get_user_profile(provider: str, client: Any, token: Any) -> dict:
    """Получает профиль пользователя от провайдера OAuth"""
    # Простые провайдеры с обработкой через lambda
    if provider in PROVIDER_HANDLERS:
        return PROVIDER_HANDLERS[provider](token, None)

    # Провайдеры требующие API вызовов
    profile_fetchers = {
        "github": _fetch_github_profile,
        "facebook": _fetch_facebook_profile,
        "x": _fetch_x_profile,
        "vk": _fetch_vk_profile,
        "yandex": _fetch_yandex_profile,
    }

    if provider in profile_fetchers:
        return await profile_fetchers[provider](client, token)

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
    if provider not in PROVIDER_CONFIGS:
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


async def oauth_callback(request: Any) -> JSONResponse | RedirectResponse:
    """
    Обработчик OAuth callback.
    Создает или обновляет пользователя и устанавливает сессионный токен.
    """
    try:
        provider = request.path_params.get("provider")
        if not provider:
            return JSONResponse({"error": "Provider not specified"}, status_code=400)

        # Получаем OAuth клиента
        client = oauth.create_client(provider)
        if not client:
            return JSONResponse({"error": "Invalid provider"}, status_code=400)

        # Получаем токен
        token = await client.authorize_access_token(request)
        if not token:
            return JSONResponse({"error": "Failed to get access token"}, status_code=400)

        # Получаем профиль пользователя
        profile = await get_user_profile(provider, client, token)
        if not profile:
            return JSONResponse({"error": "Failed to get user profile"}, status_code=400)

        # Создаем или обновляем пользователя
        author = await _create_or_update_user(provider, profile)
        if not author:
            return JSONResponse({"error": "Failed to create/update user"}, status_code=500)

        # Создаем сессию
        session_token = await TokenStorage.create_session(
            str(author.id),
            auth_data={
                "provider": provider,
                "profile": profile,
            },
            username=author.name,
            device_info={
                "user_agent": request.headers.get("user-agent"),
                "ip": request.client.host if hasattr(request, "client") else None,
            },
        )

        # Получаем state из Redis для редиректа
        state = request.query_params.get("state")
        state_data = await get_oauth_state(state) if state else None
        redirect_uri = state_data.get("redirect_uri") if state_data else FRONTEND_URL

        # Создаем ответ с редиректом
        response = RedirectResponse(url=redirect_uri)

        # Устанавливаем cookie с сессией
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_token,
            httponly=SESSION_COOKIE_HTTPONLY,
            secure=SESSION_COOKIE_SECURE,
            samesite=SESSION_COOKIE_SAMESITE,
            max_age=SESSION_COOKIE_MAX_AGE,
            path="/",  # Важно: устанавливаем path="/" для доступности cookie во всех путях
        )

        logger.info(f"OAuth успешно завершен для {provider}, user_id={author.id}")
        return response

    except Exception as e:
        logger.error(f"OAuth callback error: {e!s}")
        # В случае ошибки редиректим на фронтенд с ошибкой
        fallback_redirect = request.query_params.get("redirect_uri", FRONTEND_URL)
        return RedirectResponse(url=f"{fallback_redirect}?error=auth_failed")


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
        if not provider or provider not in PROVIDER_CONFIGS:
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

        # Создаем или обновляем пользователя используя helper функцию
        author = await _create_or_update_user(provider, profile)

        # Создаем токен сессии
        session_token = await TokenStorage.create_session(str(author.id))

        # Очищаем OAuth сессию
        request.session.pop("code_verifier", None)
        request.session.pop("provider", None)
        request.session.pop("state", None)

        # Возвращаем redirect с cookie
        response = RedirectResponse(url="/auth/success", status_code=307)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_token,
            httponly=SESSION_COOKIE_HTTPONLY,
            secure=SESSION_COOKIE_SECURE,
            samesite=SESSION_COOKIE_SAMESITE,
            max_age=SESSION_COOKIE_MAX_AGE,
        )
        return response

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return JSONResponse({"error": "OAuth callback failed"}, status_code=500)


async def _create_or_update_user(provider: str, profile: dict) -> Author:
    """
    Создает или обновляет пользователя на основе OAuth профиля.
    Возвращает объект Author.
    """
    # Для некоторых провайдеров (X, Telegram) email может отсутствовать
    email = profile.get("email")
    if not email:
        # Генерируем временный email на основе провайдера и ID
        email = _generate_temp_email(provider, profile.get("id", "unknown"))
        logger.info(f"Generated temporary email for {provider} user: {email}")

    # Создаем или обновляем пользователя
    session = get_session()
    try:
        # Сначала ищем пользователя по OAuth
        author = Author.find_by_oauth(provider, profile["id"], session)

        if author:
            # Пользователь найден по OAuth - обновляем данные
            author.set_oauth_account(provider, profile["id"], email=profile.get("email"))
            _update_author_profile(author, profile)
        else:
            # Ищем пользователя по email если есть настоящий email
            author = None
            if email and not email.endswith(TEMP_EMAIL_SUFFIX):
                author = session.query(Author).filter(Author.email == email).first()

            if author:
                # Пользователь найден по email - добавляем OAuth данные
                author.set_oauth_account(provider, profile["id"], email=profile.get("email"))
                _update_author_profile(author, profile)
            else:
                # Создаем нового пользователя
                author = _create_new_oauth_user(provider, profile, email, session)

        session.commit()
        return author
    finally:
        session.close()


def _update_author_profile(author: Author, profile: dict) -> None:
    """Обновляет профиль автора данными из OAuth"""
    if profile.get("name") and not author.name:
        author.name = profile["name"]  # type: ignore[assignment]
    if profile.get("picture") and not author.pic:
        author.pic = profile["picture"]  # type: ignore[assignment]
    author.updated_at = int(time.time())  # type: ignore[assignment]
    author.last_seen = int(time.time())  # type: ignore[assignment]


def _create_new_oauth_user(provider: str, profile: dict, email: str, session: Any) -> Author:
    """Создает нового пользователя из OAuth профиля"""
    slug = generate_unique_slug(profile["name"] or f"{provider}_{profile.get('id', 'user')}")

    author = Author(
        email=email,
        name=profile["name"] or f"{provider.title()} User",
        slug=slug,
        pic=profile.get("picture"),
        email_verified=bool(profile.get("email")),
        created_at=int(time.time()),
        updated_at=int(time.time()),
        last_seen=int(time.time()),
    )
    session.add(author)
    session.flush()  # Получаем ID автора

    # Добавляем OAuth данные для нового пользователя
    author.set_oauth_account(provider, profile["id"], email=profile.get("email"))
    return author
