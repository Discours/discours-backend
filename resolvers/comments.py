from orm import Comment, CommentRating
from orm.base import local_session
from orm.shout import ShoutCommentsSubscription
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio
from datetime import datetime

def comments_subscribe(user, slug, auto = False):
	with local_session() as session:
		sub = session.query(ShoutCommentsSubscription).\
			filter(ShoutCommentsSubscription.subscriber == user.slug, ShoutCommentsSubscription.shout == slug).\
			first()
		if auto and sub:
			return
		elif not auto and sub:
			if not sub.deletedAt is None:
				sub.deletedAt = None
				sub.auto = False
				session.commit()
				return
			raise Exception("subscription already exist")

	ShoutCommentsSubscription.create(
		subscriber = user.slug, 
		shout = slug,
		auto = auto)

def comments_unsubscribe(user, slug):
	with local_session() as session:
		sub = session.query(ShoutCommentsSubscription).\
			filter(ShoutCommentsSubscription.subscriber == user.slug, ShoutCommentsSubscription.shout == slug).\
			first()
		if not sub:
			raise Exception("subscription not exist")
		if sub.auto:
			sub.deletedAt = datetime.now()
		else:
			session.delete(sub)
		session.commit()

@mutation.field("createComment")
@login_required
async def create_comment(_, info, body, shout, replyTo = None):
	user = info.context["request"].user

	comment = Comment.create(
		author = user.id,
		body = body,
		shout = shout,
		replyTo = replyTo
		)

	try:
		comments_subscribe(user, shout, True)
	except Exception as e:
		print(f"error on comment autosubscribe: {e}")

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
			filter(CommentRating.comment_id == id, CommentRating.createdBy == user_id).first()
		if rating:
			rating.value = value
			session.commit()
	
	if not rating:
		CommentRating.create(
			comment_id = id,
			createdBy = user_id,
			value = value)

	return {}

def get_subscribed_shout_comments(slug):
	with local_session() as session:
		rows = session.query(ShoutCommentsSubscription.shout).\
			filter(ShoutCommentsSubscription.subscriber == slug, ShoutCommentsSubscription.deletedAt == None).\
			all()
	slugs = [row.shout for row in rows]
	return slugs
