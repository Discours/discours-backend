import asyncio
from orm import Proposal, ProposalRating, UserStorage
from orm.base import local_session
from orm.shout import Shout
from sqlalchemy.orm import selectinload
from orm.user import User
from resolvers.base import mutation, query
from auth.authenticate import login_required
from datetime import datetime


class ProposalResult:
	def __init__(self, status, proposal):
		self.status = status
		self.proposal = proposal

class ProposalStorage:
	lock = asyncio.Lock()
	subscriptions = []

	@staticmethod
	async def register_subscription(subs):
		async with ProposalStorage.lock:
			ProposalStorage.subscriptions.append(subs)
	
	@staticmethod
	async def del_subscription(subs):
		async with ProposalStorage.lock:
			ProposalStorage.subscriptions.remove(subs)
	
	@staticmethod
	async def put(message_result):
		async with ProposalStorage.lock:
			for subs in ProposalStorage.subscriptions:
				if message_result.message["chatId"] == subs.chat_id:
					subs.queue.put_nowait(message_result)



@query.field("getShoutProposals")
@login_required
async def get_shout_proposals(_, info, slug):
	auth = info.context["request"].auth
	user_id = auth.user_id
	with local_session() as session:
		proposals = session.query(Proposal).\
			options(selectinload(Proposal.ratings)).\
			filter(Proposal.shout == slug).\
			group_by(Proposal.id).all()
		shout = session.query(Shout).filter(Shout.slug == slug).first()
		authors = [author.id for author in shout.authors]
		if user_id not in authors:
			return {"error": "access denied"}
	for proposal in proposals:
		proposal.createdBy = await UserStorage.get_user(proposal.createdBy)
	return proposals


@mutation.field("createProposal")
@login_required
async def create_proposal(_, info, body, shout, range = None):
	auth = info.context["request"].auth
	user_id = auth.user_id

	proposal = Proposal.create(
		createdBy = user_id,
		body = body,
		shout = shout,
		range = range
		)

	result = ProposalResult("NEW", proposal)
	await ProposalStorage.put(result)

	return {"proposal": proposal}

@mutation.field("updateProposal")
@login_required
async def update_proposal(_, info, id, body):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		shout = session.query(Shout).filter(Shout.sllug == proposal.shout).first()
		authors = [author.id for author in shout.authors]
		if not proposal:
			return {"error": "invalid proposal id"}
		if proposal.author in authors:
			return {"error": "access denied"}
		proposal.body = body
		proposal.updatedAt = datetime.now()
		session.commit()

	result = ProposalResult("UPDATED", proposal)
	await ProposalStorage.put(result)

	return {"proposal": proposal}

@mutation.field("deleteProposal")
@login_required
async def delete_proposal(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		if not proposal:
			return {"error": "invalid proposal id"}
		if proposal.createdBy != user_id: 
			return {"error": "access denied"}

		proposal.deletedAt = datetime.now()
		session.commit()

	result = ProposalResult("DELETED", proposal)
	await ProposalStorage.put(result)

	return {}

@mutation.field("disableProposal")
@login_required
async def disable_proposal(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		if not proposal:
			return {"error": "invalid proposal id"}
		if proposal.createdBy != user_id: 
			return {"error": "access denied"}

		proposal.deletedAt = datetime.now()
		session.commit()

	result = ProposalResult("DISABLED", proposal)
	await ProposalStorage.put(result)

	return {}

@mutation.field("rateProposal")
@login_required
async def rate_proposal(_, info, id, value):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		if not proposal:
			return {"error": "invalid proposal id"}

		rating = session.query(ProposalRating).\
			filter(ProposalRating.proposal_id == id and ProposalRating.createdBy == user_id).first()
		if rating:
			rating.value = value
			session.commit()
	
	if not rating:
		ProposalRating.create(
			proposal_id = id,
			createdBy = user_id,
			value = value)

	result = ProposalResult("UPDATED_RATING", proposal)
	await ProposalStorage.put(result)

	return {}


@mutation.field("acceptProposal")
@login_required
async def accept_proposal(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		shout = session.query(Shout).filter(Shout.slug == proposal.shout).first()
		authors = [author.id for author in shout.authors]
		if not proposal:
			return {"error": "invalid proposal id"}
		if user_id not in authors:
			return {"error": "access denied"}

		proposal.acceptedAt = datetime.now()
		proposal.acceptedBy = user_id 
		session.commit()

	result = ProposalResult("ACCEPTED", proposal)
	await ProposalStorage.put(result)

	return {}

@mutation.field("declineProposal")
@login_required
async def decline_proposal(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		shout = session.query(Shout).filter(Shout.slug == proposal.shout).first()
		authors = [author.id for author in shout.authors]
		if not proposal:
			return {"error": "invalid proposal id"}
		if user_id not in authors:
			return {"error": "access denied"}

		proposal.acceptedAt = datetime.now()
		proposal.acceptedBy = user_id 
		session.commit()

	result = ProposalResult("DECLINED", proposal)
	await ProposalStorage.put(result)

	return {}


@mutation.field("inviteAuthor")
@login_required
async def invite_author(_, info, author, shout):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		shout = session.query(Shout).filter(Shout.slug == shout).first()
		if not shout:
			return {"error": "invalid shout slug"}
		authors = [a.id for a in shout.authors]
		if user_id not in authors:
			return {"error": "access denied"}
		author = session.query(User).filter(User.slug == author).first()
		if author.id in authors:
			return {"error": "already added"}
		shout.authors.append(author)
		session.commit()

	# result = Result("INVITED")
	# FIXME: await ShoutStorage.put(result)

	# TODO: email notify

	return {}

@mutation.field("removeAuthor")
@login_required
async def remove_author(_, info, author, shout):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		shout = session.query(Shout).filter(Shout.slug == shout).first()
		if not shout:
			return {"error": "invalid shout slug"}
		authors = [author.id for author in shout.authors]
		if user_id not in authors:
			return {"error": "access denied"}
		author = session.query(User).filter(User.slug == author).first()
		if author.id not in authors:
			return {"error": "not in authors"}
		shout.authors.remove(author)
		session.commit()

	# result = Result("INVITED")
	# FIXME: await ShoutStorage.put(result)

	# TODO: email notify

	return {}
