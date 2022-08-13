
import asyncio
from sqlalchemy.orm import selectinload
from orm.rbac import Role

class RoleStorage:
	roles = {}
	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = RoleStorage
		roles = session.query(Role).\
			options(selectinload(Role.permissions)).all()
		self.roles = dict([(role.id, role) for role in roles])
		print('[auth.roles] %d precached' % len(roles))
		

	@staticmethod
	async def get_role(id):
		self = RoleStorage
		async with self.lock:
			return self.roles.get(id)

	@staticmethod
	async def add_role(role):
		self = RoleStorage
		async with self.lock:
			self.roles[id] = role

	@staticmethod
	async def del_role(id):
		self = RoleStorage
		async with self.lock:
			del self.roles[id]