from datetime import datetime, timedelta

from auth.jwtcodec import JWTCodec
from redis import redis
from settings import JWT_LIFE_SPAN
from auth.validations import User

class TokenStorage:
	@staticmethod
	async def save(token_key, life_span, auto_delete=True):
		await redis.execute("SET", token_key, "True")
		if auto_delete:
			expire_at = (datetime.now() + timedelta(seconds=life_span)).timestamp()
			await redis.execute("EXPIREAT", token_key, int(expire_at))

	@staticmethod
	async def exist(token_key):
		return await redis.execute("GET", token_key)


class Authorize:
	@staticmethod
	async def authorize(user: User, device: str = "pc", life_span = JWT_LIFE_SPAN, auto_delete=True) -> str:
		exp = datetime.utcnow() + timedelta(seconds=life_span)
		token = JWTCodec.encode(user, exp=exp, device=device)
		await TokenStorage.save(f"{user.id}-{token}", life_span, auto_delete)
		return token

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
	async def revoke_all(user: User):
		tokens = await redis.execute("KEYS", f"{user.id}-*")
		await redis.execute("DEL", *tokens)
