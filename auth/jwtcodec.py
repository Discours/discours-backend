from datetime import datetime

import jwt

from validations.auth import TokenPayload
from settings import JWT_ALGORITHM, JWT_SECRET_KEY


class JWTCodec:
    @staticmethod
    def encode(user_id: int, exp: datetime) -> str:
        payload = {
            "user_id": user_id,
            # "user_email": user.email,  # less secure
            # "device": device,  # no use cases
            "exp": exp,
            "iat": datetime.utcnow()
        }
        try:
            return jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM)
        except Exception as e:
            print('[jwtcodec] JWT encode error %r' % e)

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                key=JWT_SECRET_KEY,
                options={
                    "verify_exp": verify_exp,
                    "verify_signature": False
                },
                algorithms=[JWT_ALGORITHM],
            )
            r = TokenPayload(**payload)
            print('[jwtcodec] debug payload %r' % r)
            return r
        except Exception as e:
            print('[jwtcodec] JWT decode error %r' % e)
