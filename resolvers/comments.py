from orm import Comment, CommentRating
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio
from datetime import datetime

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
		rating = session.query(CommentRating).\
			filter(CommentRating.comment_id == id and CommentRating.createdBy == user_id).first()
		if rating:
			rating.value = value
			session.commit()
			return {}
	
	CommentRating.create(
		comment_id = id,
		createdBy = user_id,
		value = value)
	
	return {}
