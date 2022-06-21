from orm import User, UserRole, Role, UserRating
from orm.user import AuthorSubscription, UserStorage
from orm.comment import Comment
from orm.base import local_session
from orm.topic import Topic, TopicSubscription
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required

from inbox_resolvers.inbox import get_total_unread_messages_for_user

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import selectinload
import asyncio

def _get_user_subscribed_topic_slugs(slug):
	with local_session() as session:
		rows = session.query(Topic.slug).\
			join(TopicSubscription).\
			where(TopicSubscription.subscriber == slug).\
			all()
	slugs = [row.slug for row in rows]
	return slugs

def _get_user_subscribed_authors(slug):
	with local_session() as session:
		authors = session.query(User.slug).\
			join(AuthorSubscription, User.slug == AuthorSubscription.author).\
			where(AuthorSubscription.subscriber == slug)
	return authors

async def get_user_info(slug):
	return {
		"totalUnreadMessages"      : await get_total_unread_messages_for_user(slug),
		"userSubscribedTopics"     : _get_user_subscribed_topic_slugs(slug),
		"userSubscribedAuthors"    : _get_user_subscribed_authors(slug),
		"userSubscribedCommunities": get_subscribed_communities(slug)
	}

@query.field("getCurrentUser")
@login_required
async def get_current_user(_, info):
	user = info.context["request"].user
	return {
		"user": user,
		"info": await get_user_info(user.slug)
	}

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
	return _get_user_subscribed_authors(slug)

@query.field("userSubscribers")
async def user_subscribers(_, info, slug):
	with local_session() as session:
		users = session.query(User).\
			join(AuthorSubscription, User.slug == AuthorSubscription.subscriber).\
			where(AuthorSubscription.author == slug)
	return users

@query.field("userSubscribedTopics")
async def user_subscribed_topics(_, info, slug):
	return _get_user_subscribed_topic_slugs(slug)

@mutation.field("rateUser")
@login_required
async def rate_user(_, info, slug, value):
	user = info.context["request"].user

	with local_session() as session:
		rating = session.query(UserRating).\
			filter(and_(UserRating.rater == user.slug, UserRating.user == slug)).\
			first()

		if rating:
			rating.value = value
			session.commit()
			return {}

	UserRating.create(
		rater = user.slug, 
		user = slug,
		value = value
	)

	return {}


def author_subscribe(user, slug):
	AuthorSubscription.create(
		subscriber = user.slug, 
		author = slug
	)

def author_unsubscribe(user, slug):
	with local_session() as session:
		sub = session.query(AuthorSubscription).\
			filter(and_(AuthorSubscription.subscriber == user.slug, AuthorSubscription.author == slug)).\
			first()
		if not sub:
			raise Exception("subscription not exist")
		session.delete(sub)
		session.commit()

@query.field("shoutsRatedByUser")
@login_required
async def shouts_rated_by_user(_, info, page, size):
	user = info.context["request"].user

	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutRating).\
			where(ShoutRating.rater == user.slug).\
			order_by(desc(ShoutRating.ts)).\
			limit(size).\
			offset( (page - 1) * size)

	return {
		"shouts" : shouts
	}

@query.field("userUnpublishedShouts")
@login_required
async def user_unpublished_shouts(_, info, page, size):
	user = info.context["request"].user

	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutAuthor).\
			where(and_(Shout.publishedAt == None, ShoutAuthor.user == user.slug)).\
			order_by(desc(Shout.createdAt)).\
			limit(size).\
			offset( (page - 1) * size)

	return {
		"shouts" : shouts
	}

@query.field("shoutsReviewed")
@login_required
async def shouts_reviewed(_, info, page, size):
	user = info.context["request"].user
	with local_session() as session:
		shouts_by_rating = session.query(Shout).\
			join(ShoutRating).\
			where(and_(Shout.publishedAt != None, ShoutRating.rater == user.slug))
		shouts_by_comment = session.query(Shout).\
			join(Comment).\
			where(and_(Shout.publishedAt != None, Comment.author == user.id))
		shouts = shouts_by_rating.union(shouts_by_comment).\
			order_by(desc(Shout.publishedAt)).\
			limit(size).\
			offset( (page - 1) * size)

	return shouts

@query.field("shoutCommentsSubscribed")
@login_required
async def shout_comments_subscribed(_, info, slug, page, size):
	user = info.context["request"].user
	with local_session() as session:
		comments_by_shout = session.query(Comment).\
			join(ShoutCommentsSubscription).\
			join(ShoutCommentsSubscription, ShoutCommentsSubscription.shout == slug).\
			where(ShoutCommentsSubscription.subscriber == user.slug)
		comments = comments_by_shout.\
			order_by(desc(Shout.createdAt)).\
			limit(size).\
			offset( (page - 1) * size)

	return shouts

@query.field("shoutsCommentedByUser")
async def shouts_commented_by_user(_, info, slug, page, size):
	user = await UserStorage.get_user_by_slug(slug)
	if not user:
		return {}

	with local_session() as session:
		shouts = session.query(Shout).\
			join(Comment).\
			where(Comment.author == user.id).\
			order_by(desc(Comment.createdAt)).\
			limit(size).\
			offset( (page - 1) * size)
	return shouts

