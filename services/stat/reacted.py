import asyncio
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm.attributes import flag_modified
from base.orm import Base, local_session
from orm.reaction import ReactionKind

class ReactedByDay(Base):
	__tablename__ = "reacted_by_day"

	id = None
	reaction = Column(ForeignKey("reaction.id"), primary_key = True)
	shout = Column(ForeignKey('shout.slug'), primary_key=True)
	reply = Column(ForeignKey('reaction.id'), primary_key=True, nullable=True)
	kind = Column(ReactionKind, primary_key=True)
	day = Column(DateTime, primary_key=True, default=datetime.now)

class ReactedStorage:
	reacted = {
		'shouts': {
			'total': 0,
			'today': 0,
			'month': 0,
			# TODO: need an opionated metrics list
       	},
		'topics': {} # TODO: get sum reactions for all shouts in topic
	}
	this_day_reactions = {}
	to_flush = []
	period = 30*60  # sec
	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = ReactedStorage
		reactions = session.query(ReactedByDay).all()

		for reaction in reactions:
			shout = reaction.shout
			value = reaction.value
			if shout:
				old_value = self.reacted['shouts'].get(shout, 0)
				self.reacted['shouts'][shout] = old_value + value
			if not shout in self.this_day_reactions:
				self.this_day_reactions[shout] = reaction
			this_day_reaction = self.this_day_reactions[shout]
			if this_day_reaction.day < reaction.day:
				self.this_day_reactions[shout] = reaction
		
		print('[service.reacted] watching %d shouts' % len(reactions))
		# TODO: add reactions ?

	@staticmethod
	async def get_shout(shout_slug):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['shouts'].get(shout_slug, 0)
	
	# NOTE: this method is never called
	@staticmethod
	async def get_reaction(reaction_id):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['reactions'].get(reaction_id, 0)

	@staticmethod
	async def inc_shout(shout_slug):
		self = ReactedStorage
		async with self.lock:
			this_day_reaction = self.this_day_reactions.get(shout_slug)
			day_start = datetime.now().replace(hour=0, minute=0, second=0)
			if not this_day_reaction or this_day_reaction.day < day_start:
				if this_day_reaction and getattr(this_day_reaction, "modified", False):
					self.to_flush.append(this_day_reaction)
				this_day_reaction = ReactedByDay.create(shout=shout_slug, value=1)
				self.this_day_reactions[shout_slug] = this_day_reaction
			else:
				this_day_reaction.value = this_day_reaction.value + 1
			this_day_reaction.modified = True
			old_value = self.reacted['shouts'].get(shout_slug, 0)
			self.reacted['shotus'][shout_slug] = old_value + 1

	@staticmethod
	async def inc_reaction(shout_slug, reaction_id):
		self = ReactedStorage
		async with self.lock:
			this_day_reaction = self.this_day_reactions.get(reaction_id)
			day_start = datetime.now().replace(hour=0, minute=0, second=0)
			if not this_day_reaction or this_day_reaction.day < day_start:
				if this_day_reaction and getattr(this_day_reaction, "modified", False):
					self.to_flush.append(this_day_reaction)
				this_day_reaction = ReactedByDay.create(
					shout=shout_slug, reaction=reaction_id, value=1)
				self.this_day_reactions[shout_slug] = this_day_reaction
			else:
				this_day_reaction.value = this_day_reaction.value + 1
			this_day_reaction.modified = True
			old_value = self.reacted['shouts'].get(shout_slug, 0)
			self.reacted['shouts'][shout_slug] = old_value + 1
			old_value = self.reacted['reactions'].get(shout_slug, 0)
			self.reacted['reaction'][reaction_id] = old_value + 1

	@staticmethod
	async def flush_changes(session):
		self = ReactedStorage
		async with self.lock:
			for reaction in self.this_day_reactions.values():
				if getattr(reaction, "modified", False):
					session.add(reaction)
					flag_modified(reaction, "value")
					reaction.modified = False
			for reaction in self.to_flush:
				session.add(reaction)
			self.to_flush.clear()
		session.commit()

	@staticmethod
	async def worker():
		while True:
			try:
				with local_session() as session:
					await ReactedStorage.flush_changes(session)
					print("[service.reacted] service flushed changes")
			except Exception as err:
				print("[service.reacted] errror: %s" % (err))
			await asyncio.sleep(ReactedStorage.period)
