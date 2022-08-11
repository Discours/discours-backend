
import asyncio
from base.orm import local_session
from orm.shout import ShoutAuthor


class ShoutAuthorStorage:
	authors_by_shout = {}
	lock = asyncio.Lock()
	period = 30*60 #sec

	@staticmethod
	async def load(session):
		self = ShoutAuthorStorage
		authors = session.query(ShoutAuthor).all()
		for author in authors:
			user = author.user
			shout = author.shout
			if shout in self.authors_by_shout:
				self.authors_by_shout[shout].append(user)
			else:
				self.authors_by_shout[shout] = [user]
		print('[service.shoutauthor] %d authors ' % len(self.authors_by_shout))
  # FIXME: [service.shoutauthor] 4251 authors 

	@staticmethod
	async def get_authors(shout):
		self = ShoutAuthorStorage
		async with self.lock:
			return self.authors_by_shout.get(shout, [])

	@staticmethod
	async def worker():
		self = ShoutAuthorStorage
		while True:
			try:
				with local_session() as session:
					async with self.lock:
						await self.load(session)
						print("[service.shoutauthor] updated")
			except Exception as err:
				print("[service.shoutauthor] errror: %s" % (err))
			await asyncio.sleep(self.period)