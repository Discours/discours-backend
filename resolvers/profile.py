from orm import User, UserRole, Role, UserRating
from orm.user import AuthorSubscription, UserStorage
from orm.comment import Comment
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import selectinload
import asyncio

@query.field("getCurrentUser")
@login_required
async def get_current_user(_, info):
	user = info.context["request"].user
	return { "user": user }

@query.field("getUsersBySlugs")
async def get_users_by_slugs(_, info, slugs):
	with local_session() as session:
		users = session.query(User).\
			options(selectinload(User.ratings)).\
			filter(User.slug.in_(slugs)).all()
	return users

@query.field("getUserRoles")
async def get_user_roles(_, info, slug):

	with local_session() as session:
		user = session.query(User).where(User.slug == slug).first()

		roles = session.query(Role).\
			options(selectinload(Role.permissions)).\
			join(UserRole).\
			where(UserRole.user_id == user.id).all()

	return roles

@mutation.field("updateProfile")
@login_required
async def update_profile(_, info, profile):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
		user.update(profile)
		session.commit()

	return {}

@query.field("userComments")
async def user_comments(_, info, slug, page, size):
	user = await UserStorage.get_user_by_slug(slug)
	if not user:
		return

	page = page - 1
	with local_session() as session:
		comments = session.query(Comment).\
			filter(Comment.author == user.id).\
			order_by(desc(Comment.createdAt)).\
			limit(size).\
			offset(page * size)

	return comments

@query.field("userSubscriptions")
async def user_subscriptions(_, info, slug):
	with local_session() as session:
		users = session.query(User).\
			join(AuthorSubscription, User.slug == AuthorSubscription.author).\
			where(AuthorSubscription.subscriber == slug)
	return users

@query.field("userSubscribers")
async def user_subscribers(_, info, slug):
	with local_session() as session:
		users = session.query(User).\
			join(AuthorSubscription, User.slug == AuthorSubscription.subscriber).\
			where(AuthorSubscription.author == slug)
	return users

@mutation.field("authorSubscribe")
@login_required
async def author_subscribe(_, info, slug):
	user = info.context["request"].user

	AuthorSubscription.create(
		subscriber = user.slug, 
		author = slug
	)

	return {}

@mutation.field("authorUnsubscribe")
@login_required
async def author_unsubscribe(_, info, slug):
	user = info.context["request"].user

	with local_session() as session:
		sub = session.query(AuthorSubscription).\
			filter(and_(AuthorSubscription.subscriber == user.slug, AuthorSubscription.author == slug)).\
			first()
		if not sub:
			return { "error" : "subscription not exist" }
		session.delete(sub)
		session.commit()

	return {}
