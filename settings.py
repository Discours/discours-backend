from pathlib import Path

PORT = 24579

SQLITE_URI = Path(__file__).parent / "database.sqlite3"
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = "8f1bd7696ffb482d8486dfbc6e7d16dd-secret-key"
JWT_LIFE_SPAN = 24 * 60 * 60  # seconds
JWT_AUTH_HEADER = "Auth"
REDIS_URL = "redis://127.0.0.1"
