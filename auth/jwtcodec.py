from datetime import datetime

import jwt

from validations.auth import TokenPayload, AuthInput
from settings import JWT_ALGORITHM, JWT_SECRET_KEY


class JWTCodec:
    @staticmethod
    def encode(user: AuthInput, exp: datetime) -> str:
        payload = {
            "user_id": user.id,
            # "user_email": user.email,  # less secure
            # "device": device,  # no use cases
            "exp": exp,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM)

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY,
            options={"verify_exp": verify_exp},
            algorithms=[JWT_ALGORITHM],
        )
        return TokenPayload(**payload)
