from auth.password import Password
from exceptions import InvalidPassword, ObjectNotExist
from orm import User as OrmUser
from orm.base import global_session
from validations import User


class Identity:
    @staticmethod
    def identity(user_id: int, password: str) -> User:
        user = global_session.query(OrmUser).filter_by(id=user_id).first()
        if not user:
            raise ObjectNotExist("User does not exist")
        user = User(**user.dict())
        if not Password.verify(password, user.password):
            raise InvalidPassword("Wrong user password")
        return user
