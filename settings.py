from pathlib import Path
from os import environ

PORT = 80

DB_URL = environ.get("DB_URL") or "postgresql://postgres:postgres@localhost/discours"
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = "8f1bd7696ffb482d8486dfbc6e7d16dd-secret-key"
JWT_LIFE_SPAN = 24 * 60 * 60  # seconds
JWT_AUTH_HEADER = "Auth"
REDIS_URL = environ.get("REDIS_URL") or "redis://127.0.0.1"

OAUTH_PROVIDERS = ("GITHUB", "FACEBOOK", "GOOGLE")
OAUTH_CLIENTS = {}
for provider in OAUTH_PROVIDERS:
	OAUTH_CLIENTS[provider] = {
		"id" : environ.get(provider + "_OAUTH_ID"),
		"key" : environ.get(provider + "_OAUTH_KEY")
	}
	
SHOUTS_REPO = "content"
