from datetime import datetime, timedelta

from auth.token import Token
from redis import redis
from settings import JWT_LIFE_SPAN
from auth.validations import User


class Authorize:
    @staticmethod
    async def authorize(user: User, device: str = "pc", life_span = JWT_LIFE_SPAN, auto_delete=True) -> str:
        """
        :param user:
        :param device:
        :param auto_delete: Whether the expiration is automatically deleted, the default is True
        :return:
        """
        exp = datetime.utcnow() + timedelta(seconds=life_span)
        token = Token.encode(user, exp=exp, device=device)
        await redis.execute("SET", f"{user.id}-{token}", "True")
        if auto_delete:
            expire_at = (exp + timedelta(seconds=JWT_LIFE_SPAN)).timestamp()
            await redis.execute("EXPIREAT", f"{user.id}-{token}", int(expire_at))
        return token

    @staticmethod
    async def revoke(token: str) -> bool:
        try:
            payload = Token.decode(token)
        except:  # noqa
            pass
        else:
            await redis.execute("DEL", f"{payload.user_id}-{token}")
        return True

    @staticmethod
    async def revoke_all(user: User):
        tokens = await redis.execute("KEYS", f"{user.id}-*")
        await redis.execute("DEL", *tokens)
