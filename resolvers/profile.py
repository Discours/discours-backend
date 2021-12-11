from orm import User, UserRole, Role, UserRating
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required

from sqlalchemy import func
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
