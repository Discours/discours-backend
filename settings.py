from os import environ

PORT = 8080
INBOX_SERVICE_PORT = 8081

BACKEND_URL = environ.get("BACKEND_URL") or "https://localhost:8080"
OAUTH_CALLBACK_URL = environ.get("OAUTH_CALLBACK_URL") or "https://localhost:8080"
CONFIRM_CALLBACK_URL = "https://new.discours.io/confirm"
CONFIRM_EMAIL_URL = environ.get("AUTH_CONFIRM_URL") or BACKEND_URL + "/confirm"
ERROR_URL_ON_FRONTEND = (
    environ.get("ERROR_URL_ON_FRONTEND") or "https://new.discours.io"
)

DB_URL = (
    environ.get("DATABASE_URL") or environ.get("DB_URL") or
    "postgresql://postgres@localhost:5432/discoursio" or "sqlite:///db.sqlite3"
)
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = "8f1bd7696ffb482d8486dfbc6e7d16dd-secret-key"
SESSION_TOKEN_HEADER = "Auth"
SESSION_TOKEN_LIFE_SPAN = 24 * 60 * 60  # seconds
ONETIME_TOKEN_LIFE_SPAN = 1 * 60 * 60  # seconds
REDIS_URL = environ.get("REDIS_URL") or "redis://127.0.0.1"

MAILGUN_API_KEY = environ.get("MAILGUN_API_KEY")
MAILGUN_DOMAIN = environ.get("MAILGUN_DOMAIN")

OAUTH_PROVIDERS = ("GITHUB", "FACEBOOK", "GOOGLE")
OAUTH_CLIENTS = {}
for provider in OAUTH_PROVIDERS:
    OAUTH_CLIENTS[provider] = {
        "id": environ.get(provider + "_OAUTH_ID"),
        "key": environ.get(provider + "_OAUTH_KEY"),
    }

SHOUTS_REPO = "content"
