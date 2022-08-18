import asyncio
from datetime import datetime
from sqlalchemy.types import Enum
from sqlalchemy import Column, DateTime, ForeignKey, Boolean
# from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import Enum
import enum
from base.orm import Base, local_session
from orm.topic import ShoutTopic

class ReactionKind(enum.Enum):
	AGREE 	= 1 # +1
	DISAGREE = 2 # -1
	PROOF 	= 3	# +1
	DISPROOF = 4 # -1
	ASK		= 5 # +0 bookmark
	PROPOSE	= 6 # +0
	QUOTE	= 7 # +0 bookmark
	COMMENT	= 8 # +0
	ACCEPT	= 9 # +1
	REJECT	= 0 # -1
	LIKE	= 11 # +1
	DISLIKE	= 12 # -1
	# TYPE = <reaction index> # rating diff

def kind_to_rate(kind) -> int:
	if kind in [
		ReactionKind.AGREE,
		ReactionKind.LIKE,
		ReactionKind.PROOF,
		ReactionKind.ACCEPT
	]: return 1
	elif kind in [
		ReactionKind.DISAGREE,
		ReactionKind.DISLIKE,
		ReactionKind.DISPROOF,
		ReactionKind.REJECT
	]: return -1
	else: return 0
 
class ReactedByDay(Base):
	__tablename__ = "reacted_by_day"

	id = None
	reaction = Column(ForeignKey("reaction.id"), primary_key = True)
	shout = Column(ForeignKey('shout.slug'), primary_key=True)
	replyTo = Column(ForeignKey('reaction.id'), nullable=True)
	kind: int = Column(Enum(ReactionKind), nullable=False, comment="Reaction kind")
	day = Column(DateTime, primary_key=True, default=datetime.now)
	comment = Column(Boolean, nullable=True)
	

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
	async def get_comments(shout_slug):
		self = ReactedStorage
		async with self.lock:
			return list(filter(lambda r: r.comment, self.reacted['shouts'].get(shout_slug, [])))

	@staticmethod
	async def get_topic_comments(topic_slug):
		self = ReactedStorage
		async with self.lock:
			return list(filter(lambda r: r.comment, self.reacted['topics'].get(topic_slug, [])))

	@staticmethod
	async def get_reaction_comments(reaction_id):
		self = ReactedStorage
		async with self.lock:
			return list(filter(lambda r: r.comment, self.reacted['reactions'].get(reaction_id)))

	@staticmethod
	async def get_reaction(reaction_id):
		self = ReactedStorage
		async with self.lock:
			return self.reacted['reactions'].get(reaction_id, [])

	@staticmethod
	async def get_rating(shout_slug):
		self = ReactedStorage
		rating = 0
		async with self.lock:
			for r in self.reacted['shouts'].get(shout_slug, []):
				rating = rating + kind_to_rate(r.kind)
		return rating

	@staticmethod
	async def get_topic_rating(topic_slug):
		self = ReactedStorage
		rating = 0
		async with self.lock:
			for r in self.reacted['topics'].get(topic_slug, []):
				rating = rating + kind_to_rate(r.kind)
		return rating

	@staticmethod
	async def get_reaction_rating(reaction_id):
		self = ReactedStorage
		rating = 0
		async with self.lock:
			for r in self.reacted['reactions'].get(reaction_id, []):
				rating = rating + kind_to_rate(r.kind)
		return rating

	@staticmethod
	async def increment(reaction):
		self = ReactedStorage
		async with self.lock:
			with local_session() as session:
				r = {
					"day": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
					"reaction": reaction.id,
					"kind": reaction.kind,
					"shout": reaction.shout
				}
				if reaction.replyTo: r['replyTo'] = reaction.replyTo
				if reaction.body: r['comment'] = True
				reaction = ReactedByDay.create(**r)
				self.reacted['shouts'][reaction.shout] = self.reacted['shouts'].get(reaction.shout, [])
				self.reacted['shouts'][reaction.shout].append(reaction)
				if reaction.replyTo:
					self.reacted['reaction'][reaction.replyTo] = self.reacted['reactions'].get(reaction.shout, [])
					self.reacted['reaction'][reaction.replyTo].append(reaction)
					self.rating['reactions'][reaction.replyTo] = self.rating['reactions'].get(reaction.replyTo, 0) + kind_to_rate(reaction.kind)
				else:
					self.rating['shouts'][reaction.replyTo] = self.rating['shouts'].get(reaction.shout, 0) + kind_to_rate(reaction.kind)

	@staticmethod
	def init(session):
		self = ReactedStorage
		all_reactions = session.query(ReactedByDay).all()
		print('[stat.reacted] %d reactions total' % len(all_reactions))
		for reaction in all_reactions:
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