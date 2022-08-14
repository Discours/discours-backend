
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
		sas = session.query(ShoutAuthor).all()
		for sa in sas:
			self.authors_by_shout[sa.shout] = self.authors_by_shout.get(sa.shout, [])
			self.authors_by_shout[sa.shout].append([sa.user, sa.caption])
		print('[zine.authors] %d shouts preprocessed' % len(self.authors_by_shout))

	@staticmethod
	async def get_authors(shout):
		self = ShoutAuthorStorage
		async with self.lock:
			return self.authors_by_shout.get(shout, [])

	@staticmethod
	async def get_author_caption(shout, author):
		self = ShoutAuthorStorage
		async with self.lock:
			for a in self.authors_by_shout.get(shout, []):
				if author in a:
					return a[1]
		return { "error": "author caption not found" }

	@staticmethod
	async def worker():
		self = ShoutAuthorStorage
		while True:
			try:
				with local_session() as session:
					async with self.lock:
						await self.load(session)
						print("[zine.authors] state updated")
			except Exception as err:
				print("[zine.authors] errror: %s" % (err))
			await asyncio.sleep(self.period)