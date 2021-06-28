from datetime import datetime

import jwt

from settings import JWT_ALGORITHM, JWT_SECRET_KEY
from validations import PayLoad, User


class Token:
    @staticmethod
    def encode(user: User, exp: datetime, device: str = "pc") -> str:
        payload = {"user_id": user.id, "device": device, "exp": exp, "iat": datetime.utcnow()}
        return jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM).decode("UTF-8")

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> PayLoad:
        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY,
            options={"verify_exp": verify_exp},
            algorithms=[JWT_ALGORITHM],
        )
        return PayLoad(**payload)
