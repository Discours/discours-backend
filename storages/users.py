
import asyncio
from sqlalchemy.orm import selectinload
from orm.user import User


class UserStorage:
	users = {}
	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = UserStorage
		users = session.query(User).\
			options(selectinload(User.roles), selectinload(User.ratings)).all()
			# TODO: add shouts and reactions counters
		self.users = dict([(user.id, user) for user in users])
		print('[storage.users] %d ' % len(self.users))

	@staticmethod
	async def get_user(id):
		self = UserStorage
		async with self.lock:
			return self.users.get(id)

	@staticmethod
	async def get_all_users():
		self = UserStorage
		async with self.lock:
			aaa = list(self.users.copy().values())
			aaa.sort(key=lambda user: user.createdAt)
			return aaa

	@staticmethod
	async def get_user_by_slug(slug):
		self = UserStorage
		async with self.lock:
			for user in self.users.values():
				if user.slug == slug:
					return user

	@staticmethod
	async def add_user(user):
		self = UserStorage
		async with self.lock:
			self.users[user.id] = user

	@staticmethod
	async def del_user(id):
		self = UserStorage
		async with self.lock:
			del self.users[id]