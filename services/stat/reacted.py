import asyncio
from datetime import datetime
from sqlalchemy.types import Enum
from sqlalchemy import Column, DateTime, ForeignKey, Integer
# from sqlalchemy.orm.attributes import flag_modified
from base.orm import Base, local_session
from orm.reaction import Reaction, ReactionKind, kind_to_rate
from orm.topic import ShoutTopic

class ReactedByDay(Base):
	__tablename__ = "reacted_by_day"

	id = None
	reaction = Column(ForeignKey("reaction.id"), primary_key = True)
	shout = Column(ForeignKey('shout.slug'), primary_key=True)
	reply = Column(ForeignKey('reaction.id'), nullable=True)
	kind: int = Column(Enum(ReactionKind), nullable=False, comment="Reaction kind")
	day = Column(DateTime, primary_key=True, default=datetime.now)

class ReactedStorage:
	reacted = {
		'shouts': {},
		'topics': {},
		'reactions': {}
	}
	rating = {
		'shouts': {},
		'topics': {},
		'reactions': {}
	}
	reactions = []
	to_flush = []
	period = 30*60  # sec
	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = ReactedStorage
		all_reactions = session.query(ReactedByDay).all()
		all_reactions2 = session.query(Reaction).filter(Reaction.deletedAt == None).all()
		print('[stat.reacted] %d reactions total' % len(all_reactions or all_reactions2))
		rrr = (all_reactions or all_reactions2)
		create = False
		if not all_reactions: create = True
		for reaction in rrr:
			shout = reaction.shout
			topics = session.query(ShoutTopic.topic).where(ShoutTopic.shout == shout).all()
			kind = reaction.kind
   
			self.reacted['shouts'][shout] = self.reacted['shouts'].get(shout, [])
			self.reacted['shouts'][shout].append(reaction)
			self.rating['shouts'][shout] = self.rating['shouts'].get(shout, 0) + kind_to_rate(kind)
   
			for t in topics:
				self.reacted['topics'][t] = self.reacted['topics'].get(t, [])
				self.reacted['topics'][t].append(reaction)
				self.rating['topics'][t] = self.rating['topics'].get(t, 0) + kind_to_rate(kind) # rating
	
			if reaction.replyTo:
				self.reacted['reactions'][reaction.replyTo] = self.reacted['reactions'].get(reaction.replyTo, [])
				self.reacted['reactions'][reaction.replyTo].append(reaction)
				self.rating['reactions'][reaction.replyTo] = self.rating['reactions'].get(reaction.replyTo, 0) + kind_to_rate(reaction.kind)
		ttt = self.reacted['topics'].values()
		print('[stat.reacted] %d topics reacted' % len(ttt))
		print('[stat.reacted] %d shouts reacted' % len(self.reacted['shouts']))
		print('[stat.reacted] %d reactions reacted' % len(self.reacted['reactions']))
  
		if len(all_reactions) == 0 and len(all_reactions2) != 0:
			with local_session() as session:
				for r in all_reactions2:
					session.add(ReactedByDay(reaction=r.id, shout=r.shout, reply=r.replyTo, kind=r.kind, day=r.createdAt.replace(hour=0, minute=0, second=0)))
				session.commit()

	@staticmethod
	async def get_shout(shout_slug):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['shouts'].get(shout_slug, [])
	
	@staticmethod
	async def get_topic(topic_slug):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['topics'].get(topic_slug, [])

	@staticmethod
	async def get_reaction(reaction_id):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['reactions'].get(reaction_id, [])

	@staticmethod
	async def get_rating(shout_slug):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['shouts'].get(shout_slug, 0)

	@staticmethod
	async def get_topic_rating(topic_slug):
		self = ReactedStorage
		async with self.lock:
			return self.rating['topics'].get(topic_slug, 0)

	@staticmethod
	async def get_reaction_rating(reaction_id):
		self = ReactedStorage
		async with self.lock:
			return self.rating['reactions'].get(reaction_id, 0)

	@staticmethod
	async def increment(shout_slug, kind, reply_id = None):
		self = ReactedStorage
		reaction: ReactedByDay = None
		async with self.lock:
			with local_session() as session:
				reaction = ReactedByDay.create(shout=shout_slug, kind=kind, reply=reply_id)
				self.reacted['shouts'][shout_slug] = self.reacted['shouts'].get(shout_slug, [])
				self.reacted['shouts'][shout_slug].append(reaction)
				if reply_id:
					self.reacted['reaction'][reply_id] = self.reacted['reactions'].get(shout_slug, [])
					self.reacted['reaction'][reply_id].append(reaction)
					self.rating['reactions'][reply_id] = self.rating['reactions'].get(reply_id, 0) + kind_to_rate(kind)
				else:
					self.rating['shouts'][shout_slug] = self.rating['shouts'].get(shout_slug, 0) + kind_to_rate(kind)