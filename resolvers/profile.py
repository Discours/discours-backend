from orm import User, UserRole, Role
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required

from sqlalchemy.orm import selectinload
import asyncio

@query.field("getUserBySlug") # get a public profile
async def get_user_by_slug(_, info, slug):
	with local_session() as session:
		user = session.query(User).filter(User.slug == slug).first()
	return { "user": user } # TODO: remove some fields for public


@query.field("getCurrentUser")
@login_required
async def get_current_user(_, info):
	auth = info.context["request"].auth
	user_id = auth.user_id
	with local_session() as session:
		user = session.query(User).filter(User.id == user_id).first()
	return { "user": user }

@query.field("userRoles")
@login_required
async def user_roles(_, info):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		roles = session.query(Role).\
			options(selectinload(Role.permissions)).\
			join(UserRole).\
			where(UserRole.user_id == user_id).all()

	return roles
