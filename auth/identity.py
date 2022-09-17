from jwt import DecodeError, ExpiredSignatureError
from sqlalchemy import or_

from auth.jwtcodec import JWTCodec
from auth.tokenstorage import TokenStorage
from validations.auth import AuthInput
from base.exceptions import InvalidPassword
from base.exceptions import InvalidToken
from base.orm import local_session
from orm import User
from passlib.hash import bcrypt


class Password:
    @staticmethod
    def encode(password: str) -> str:
        return bcrypt.hash(password)

    @staticmethod
    def verify(password: str, other: str) -> bool:
        return bcrypt.verify(password, other)


class Identity:
    @staticmethod
    def password(orm_user: User, password: str) -> User:
        user = User(**orm_user.dict())
        if not user.password:
            raise InvalidPassword("User password is empty")
        if not Password.verify(password, user.password):
            raise InvalidPassword("Wrong user password")
        return user

    @staticmethod
    def oauth(inp: AuthInput) -> User:
        with local_session() as session:
            user = (
                session.query(User)
                .filter(or_(User.oauth == inp["oauth"], User.email == inp["email"]))
                .first()
            )
            if not user:
                user = User.create(**inp)
            if not user.oauth:
                user.oauth = inp["oauth"]
                session.commit()

        user = User(**user.dict())
        return user

    @staticmethod
    async def onetime(token: str) -> User:
        try:
            payload = JWTCodec.decode(token)
            if not await TokenStorage.exist(f"{payload.user_id}-{token}"):
                raise InvalidToken("Login token has expired, please login again")
        except ExpiredSignatureError:
            raise InvalidToken("Login token has expired, please try again")
        except DecodeError as e:
            raise InvalidToken("token format error") from e
        with local_session() as session:
            user = session.query(User).filter_by(id=payload.user_id).first()
            if not user:
                raise Exception("user not exist")
            if not user.emailConfirmed:
                user.emailConfirmed = True
                session.commit()
            return user
