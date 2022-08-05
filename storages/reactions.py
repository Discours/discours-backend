import asyncio
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import selectinload, joinedload
from orm.base import local_session
from orm.reaction import Reaction, ReactionKind
from orm.topic import ShoutTopic, Topic


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

class ReactionsStorage:
	limit = 200
	reactions = []
	rating_by_shout = {}
	reactions_by_shout = {}
	reactions_by_topic = {}  # TODO: get sum reactions for all shouts in topic
	reactions_by_author = {}
	lock = asyncio.Lock()
	period = 3*60  # 3 mins

	@staticmethod
	async def prepare_all(session):
		stmt = session.query(Reaction).\
			filter(Reaction.deletedAt == None).\
			order_by(desc("createdAt")).\
			limit(ReactionsStorage.limit)
		reactions = []
		for row in session.execute(stmt):
			reaction = row.Reaction
			reactions.append(reaction)
		reactions.sort(key=lambda x: x.createdAt, reverse=True)
		async with ReactionsStorage.lock:
			print("[storage.reactions] %d recently published reactions " % len(reactions))
			ReactionsStorage.reactions = reactions

	@staticmethod
	async def prepare_by_author(session):
		try:
			by_authors = session.query(Reaction.createdBy, func.count('*').label("count")).\
				where(and_(Reaction.deletedAt == None)).\
				group_by(Reaction.createdBy).all()
		except Exception as e:
			print(e)
			by_authors = {}
		async with ReactionsStorage.lock:
			ReactionsStorage.reactions_by_author = dict([stat for stat in by_authors])
			print("[storage.reactions] %d reacted users" % len(by_authors))

	@staticmethod
	async def prepare_by_shout(session):
		try:
			by_shouts = session.query(Reaction.shout, func.count('*').label("count")).\
				where(and_(Reaction.deletedAt == None)).\
				group_by(Reaction.shout).all()
		except Exception as e:
			print(e)
			by_shouts = {}
		async with ReactionsStorage.lock:
			ReactionsStorage.reactions_by_shout = dict([stat for stat in by_shouts])
			print("[storage.reactions] %d reacted shouts" % len(by_shouts))

	@staticmethod
	async def calc_ratings(session):
		rating_by_shout = {}
		for shout in ReactionsStorage.reactions_by_shout.keys():
			rating_by_shout[shout] = 0
			shout_reactions_by_kinds = session.query(Reaction).\
				where(and_(Reaction.deletedAt == None, Reaction.shout == shout)).\
				group_by(Reaction.kind, Reaction.id).all()
			for reaction in shout_reactions_by_kinds:
				rating_by_shout[shout] +=  kind_to_rate(reaction.kind)
		async with ReactionsStorage.lock:
			ReactionsStorage.rating_by_shout = rating_by_shout

	@staticmethod
	async def prepare_by_topic(session):
		# TODO: optimize
		by_topics = session.query(Reaction, func.count('*').label("count")).\
			options(
				joinedload(ShoutTopic),
				joinedload(Reaction.shout)
			).\
			join(ShoutTopic, ShoutTopic.shout == Reaction.shout).\
			filter(Reaction.deletedAt == None).\
			group_by(ShoutTopic.topic).all()
		reactions_by_topic = {}
		for t, reactions in by_topics:
			if not reactions_by_topic.get(t):
				reactions_by_topic[t] = 0
			for r in reactions:
				reactions_by_topic[t] += r.count
		async with ReactionsStorage.lock:
			ReactionsStorage.reactions_by_topic = reactions_by_topic

	@staticmethod
	async def recent():
		async with ReactionsStorage.lock:
			return ReactionsStorage.reactions

	@staticmethod
	async def total():
		async with ReactionsStorage.lock:
			return len(ReactionsStorage.reactions)

	@staticmethod
	async def by_shout(shout):
		async with ReactionsStorage.lock:
			stat = ReactionsStorage.reactions_by_shout.get(shout)
			stat = stat if stat else 0
			return stat
	
	@staticmethod
	async def shout_rating(shout):
		async with ReactionsStorage.lock:
			return ReactionsStorage.rating_by_shout.get(shout)

	@staticmethod
	async def by_author(slug):
		async with ReactionsStorage.lock:
			stat = ReactionsStorage.reactions_by_author.get(slug)
			stat = stat if stat else 0
			return stat

	@staticmethod
	async def by_topic(topic):
		async with ReactionsStorage.lock:
			stat = ReactionsStorage.reactions_by_topic.get(topic)
			stat = stat if stat else 0
			return stat

	@staticmethod
	async def worker():
		while True:
			try:
				with local_session() as session:
					await ReactionsStorage.prepare_all(session)
					print("[storage.reactions] all reactions prepared")
					await ReactionsStorage.prepare_by_shout(session)
					print("[storage.reactions] reactions by shouts prepared")
					await ReactionsStorage.calc_ratings(session)
					print("[storage.reactions] reactions ratings prepared")
					await ReactionsStorage.prepare_by_topic(session)
					print("[storage.reactions] reactions topics prepared")
			except Exception as err:
				print("[storage.reactions] errror: %s" % (err))
			await asyncio.sleep(ReactionsStorage.period)
