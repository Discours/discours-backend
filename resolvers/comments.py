from orm import Comment, CommentRating
from orm.base import local_session
from orm.shout import ShoutCommentsSubscription
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio
from datetime import datetime

class CommentResult:
	def __init__(self, status, comment):
		self.status = status
		self.comment = comment

class ShoutCommentsSubscription:
	queue = asyncio.Queue()

	def __init__(self, shout_slug):
		self.shout_slug = shout_slug

class ShoutCommentsStorage:
	lock = asyncio.Lock()
	subscriptions = []

	@staticmethod
	async def register_subscription(subs):
		self = ShoutCommentsStorage
		async with self.lock:
			self.subscriptions.append(subs)
	
	@staticmethod
	async def del_subscription(subs):
		self = ShoutCommentsStorage
		async with self.lock:
			self.subscriptions.remove(subs)
	
	@staticmethod
	async def put(comment_result):
		self = ShoutCommentsStorage
		async with self.lock:
			for subs in self.subscriptions:
				if comment_result.comment.shout == subs.shout_slug:
					subs.queue.put_nowait(comment_result)

def comments_subscribe(user, slug):
	ShoutCommentsSubscription.create(
		subscriber = user.slug, 
		shout = slug)

def comments_unsubscribe(user, slug):
	with local_session() as session:
		sub = session.query(ShoutCommentsSubscription).\
			filter(and_(ShoutCommentsSubscription.subscriber == user.slug, ShoutCommentsSubscription.shout == slug)).\
			first()
		if not sub:
			raise Exception("subscription not exist")
		session.delete(sub)
		session.commit()

@mutation.field("createComment")
@login_required
async def create_comment(_, info, body, shout, replyTo = None):
	auth = info.context["request"].auth
	user_id = auth.user_id

	comment = Comment.create(
		author = user_id,
		body = body,
		shout = shout,
		replyTo = replyTo
		)

	result = CommentResult("NEW", comment)
	await ShoutCommentsStorage.put(result)

	return {"comment": comment}

@mutation.field("updateComment")
@login_required
async def update_comment(_, info, id, body):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == id).first()
		if not comment:
			return {"error": "invalid comment id"}
		if comment.author != user_id:
			return {"error": "access denied"}
		
		comment.body = body
		comment.updatedAt = datetime.now()
		
		session.commit()

	result = CommentResult("UPDATED", comment)
	await ShoutCommentsStorage.put(result)

	return {"comment": comment}

@mutation.field("deleteComment")
@login_required
async def delete_comment(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == id).first()
		if not comment:
			return {"error": "invalid comment id"}
		if comment.author != user_id:
			return {"error": "access denied"}

		comment.deletedAt = datetime.now()
		session.commit()

	result = CommentResult("DELETED", comment)
	await ShoutCommentsStorage.put(result)

	return {}

@mutation.field("rateComment")
@login_required
async def rate_comment(_, info, id, value):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == id).first()
		if not comment:
			return {"error": "invalid comment id"}

		rating = session.query(CommentRating).\
			filter(CommentRating.comment_id == id and CommentRating.createdBy == user_id).first()
		if rating:
			rating.value = value
			session.commit()
	
	if not rating:
		CommentRating.create(
			comment_id = id,
			createdBy = user_id,
			value = value)

	result = CommentResult("UPDATED_RATING", comment)
	await ShoutCommentsStorage.put(result)

	return {}
