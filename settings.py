"""Настройки приложения"""

import datetime
import os
from os import environ
from pathlib import Path
from typing import Literal

# Корневая директория проекта
ROOT_DIR = Path(__file__).parent.absolute()

DEV_SERVER_PID_FILE_NAME = "dev-server.pid"

PORT = environ.get("PORT") or 8000

# storages
DB_URL = (
    environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or environ.get("DB_URL", "").replace("postgres://", "postgresql://")
    or "sqlite:///discoursio.db"
)
DATABASE_URL = DB_URL
REDIS_URL = environ.get("REDIS_URL") or "redis://127.0.0.1"

# debug
GLITCHTIP_DSN = environ.get("GLITCHTIP_DSN")

# auth
ADMIN_SECRET = environ.get("AUTH_SECRET") or "nothing"
ADMIN_EMAILS = environ.get("ADMIN_EMAILS") or "services@discours.io,guests@discours.io,welcome@discours.io"

# own auth
ONETIME_TOKEN_LIFE_SPAN = 60 * 15  # 15 минут
SESSION_TOKEN_LIFE_SPAN = 60 * 60 * 24 * 30  # 30 дней
SESSION_TOKEN_HEADER = "Authorization"
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default_secret_key_change_in_production-ok?")
JWT_ISSUER = "discours"
JWT_EXPIRATION_DELTA = datetime.timedelta(days=30)  # Токен действителен 30 дней

# URL фронтенда
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Настройки OAuth провайдеров
OAUTH_CLIENTS = {
    "GOOGLE": {
        "id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "key": os.getenv("GOOGLE_CLIENT_SECRET", ""),
    },
    "GITHUB": {
        "id": os.getenv("GITHUB_CLIENT_ID", ""),
        "key": os.getenv("GITHUB_CLIENT_SECRET", ""),
    },
    "FACEBOOK": {
        "id": os.getenv("FACEBOOK_CLIENT_ID", ""),
        "key": os.getenv("FACEBOOK_CLIENT_SECRET", ""),
    },
    "X": {
        "id": os.getenv("X_CLIENT_ID", ""),
        "key": os.getenv("X_CLIENT_SECRET", ""),
    },
    "YANDEX": {
        "id": os.getenv("YANDEX_CLIENT_ID", ""),
        "key": os.getenv("YANDEX_CLIENT_SECRET", ""),
    },
    "VK": {
        "id": os.getenv("VK_CLIENT_ID", ""),
        "key": os.getenv("VK_CLIENT_SECRET", ""),
    },
    "TELEGRAM": {
        "id": os.getenv("TELEGRAM_CLIENT_ID", ""),
        "key": os.getenv("TELEGRAM_CLIENT_SECRET", ""),
    },
}

# Настройки JWT
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(environ.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# Настройки для HTTP cookies (используется в auth middleware)
SESSION_COOKIE_NAME = "session_token"
SESSION_COOKIE_SECURE = True  # Включаем для HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 дней

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "discours.io")


TXTAI_SERVICE_URL = os.environ.get("TXTAI_SERVICE_URL", "none")
