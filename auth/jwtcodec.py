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
            "iat": datetime.utcnow()
        }
        try:
            r = jwt.encode(
                payload,
                JWT_SECRET_KEY,
                JWT_ALGORITHM
            )
            return r
        except Exception as e:
            print('[jwtcodec] JWT encode error %r' % e)

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                key=JWT_SECRET_KEY,
                options={"verify_exp": verify_exp},
                algorithms=[JWT_ALGORITHM],
            )
            return TokenPayload(**payload)
        except Exception as e:
            print('[jwtcodec] JWT decode error %r' % e)
