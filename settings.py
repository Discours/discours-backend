import sys
from os import environ

MODE = "development" if "dev" in sys.argv else "production"
DEV_SERVER_PID_FILE_NAME = "dev-server.pid"

PORT = environ.get("PORT") or 8000

# storages
DB_URL = (
    environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or environ.get("DB_URL", "").replace("postgres://", "postgresql://")
    or "sqlite:///discoursio.db"
)
REDIS_URL = environ.get("REDIS_URL") or "redis://127.0.0.1"

# debug
GLITCHTIP_DSN = environ.get("GLITCHTIP_DSN")

# authorizer.dev
AUTH_URL = environ.get("AUTH_URL") or "https://auth.discours.io/graphql"
ADMIN_SECRET = environ.get("AUTH_SECRET") or "nothing"
WEBHOOK_SECRET = environ.get("WEBHOOK_SECRET") or "nothing-else"

# own auth
ONETIME_TOKEN_LIFE_SPAN = 60 * 60 * 24 * 3  # 3 days
SESSION_TOKEN_LIFE_SPAN = 60 * 60 * 24 * 30  # 30 days
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = environ.get("JWT_SECRET") or "nothing-else-jwt-secret-matters"
