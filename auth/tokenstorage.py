from datetime import datetime, timedelta

from auth.jwtcodec import JWTCodec
from validations.auth import AuthInput
from base.redis import redis
from settings import SESSION_TOKEN_LIFE_SPAN, ONETIME_TOKEN_LIFE_SPAN


async def save(token_key, life_span, auto_delete=True):
    await redis.execute("SET", token_key, "True")
    if auto_delete:
        expire_at = (datetime.now() + timedelta(seconds=life_span)).timestamp()
        await redis.execute("EXPIREAT", token_key, int(expire_at))


class TokenStorage:
    @staticmethod
    async def get(token_key):
        return await redis.execute("GET", token_key)

    @staticmethod
    async def create_onetime(user: AuthInput) -> str:
        life_span = ONETIME_TOKEN_LIFE_SPAN
        exp = datetime.utcnow() + timedelta(seconds=life_span)
        one_time_token = JWTCodec.encode(user, exp)
        await save(f"{user.id}-{one_time_token}", life_span)
        return one_time_token

    @staticmethod
    async def create_session(user: AuthInput) -> str:
        life_span = SESSION_TOKEN_LIFE_SPAN
        exp = datetime.utcnow() + timedelta(seconds=life_span)
        session_token = JWTCodec.encode(user, exp)
        await save(f"{user.id}-{session_token}", life_span)
        return session_token

    @staticmethod
    async def revoke(token: str) -> bool:
        try:
            payload = JWTCodec.decode(token)
        except:  # noqa
            pass
        else:
            await redis.execute("DEL", f"{payload.user_id}-{token}")
        return True

    @staticmethod
    async def revoke_all(user: AuthInput):
        tokens = await redis.execute("KEYS", f"{user.id}-*")
        await redis.execute("DEL", *tokens)
