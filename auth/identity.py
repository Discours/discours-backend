from auth.password import Password
from exceptions import InvalidPassword, ObjectNotExist
from orm import User as OrmUser
from orm.base import local_session
from auth.validations import User

from sqlalchemy import or_


class Identity:
	@staticmethod
	def identity(user_id: int, password: str) -> User:
		with local_session() as session:
			user = session.query(OrmUser).filter_by(id=user_id).first()
		if not user:
			raise ObjectNotExist("User does not exist")
		user = User(**user.dict())
		if user.password is None:
			raise InvalidPassword("Wrong user password")
		if not Password.verify(password, user.password):
			raise InvalidPassword("Wrong user password")
		return user
	
	@staticmethod
	def identity_oauth(input) -> User:
		with local_session() as session:
			user = session.query(OrmUser).filter(
				or_(OrmUser.oauth == input["oauth"], OrmUser.email == input["email"])
				).first()
			if not user:
				user = OrmUser.create(**input)
			if not user.oauth:
				user.oauth = input["oauth"]
				session.commit()

		user = User(**user.dict())
		return user
