from datetime import datetime, timezone
import jwt
from base.exceptions import ExpiredToken, InvalidToken
from validations.auth import TokenPayload, AuthInput
from settings import JWT_ALGORITHM, JWT_SECRET_KEY


class JWTCodec:
    @staticmethod
    def encode(user: AuthInput, exp: datetime) -> str:
        payload = {
            "user_id": user.id,
            "username": user.email or user.phone,
            "exp": exp,
            "iat": datetime.now(tz=timezone.utc),
            "iss": "discours"
        }
        try:
            return jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM)
        except Exception as e:
            print('[auth.jwtcodec] JWT encode error %r' % e)

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        r = None
        try:
            payload = jwt.decode(
                token,
                key=JWT_SECRET_KEY,
                options={
                    "verify_exp": verify_exp,
                    # "verify_signature": False
                },
                algorithms=[JWT_ALGORITHM],
                issuer="discours"
            )
            r = TokenPayload(**payload)
            print('[auth.jwtcodec] debug token %r' % r)
            return r
        except jwt.InvalidIssuedAtError:
            print('[auth.jwtcodec] invalid issued at: %r' % payload)
            raise ExpiredToken('check token issued time')
        except jwt.ExpiredSignatureError:
            print('[auth.jwtcodec] expired signature %r' % payload)
            raise ExpiredToken('check token lifetime')
        except jwt.InvalidTokenError:
            raise InvalidToken('token is not valid')
        except jwt.InvalidSignatureError:
            raise InvalidToken('token is not valid')
