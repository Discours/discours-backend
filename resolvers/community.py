from orm import Community, CommunitySubscription
from orm.base import local_session
from resolvers.base import mutation, query
from auth.authenticate import login_required
from datetime import datetime

from sqlalchemy import and_

@mutation.field("createCommunity")
@login_required
async def create_community(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id

	community = Community.create(
		slug = input.get('slug', ''),
		title = input.get('title', ''),
		desc = input.get('desc', ''),
		pic = input.get('pic', '')
		)

	return {"community": community}

@mutation.field("updateCommunity")
@login_required
async def update_community(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		community = session.query(Community).filter(Community.slug == input.get('slug', '')).first()
		if not community:
			return {"error": "invalid community id"}
		if community.createdBy != user_id:
			return {"error": "access denied"}
		community.title = input.get('title', '')
		community.desc = input.get('desc', '')
		community.pic = input.get('pic', '')
		community.updatedAt = datetime.now()
		session.commit()

@mutation.field("deleteCommunity")
@login_required
async def delete_community(_, info, slug):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		community = session.query(Community).filter(Community.slug == slug).first()
		if not community:
			return {"error": "invalid community slug"}
		if community.owner != user_id:
			return {"error": "access denied"}
		community.deletedAt = datetime.now()
		session.commit()

	return {}

@query.field("getCommunity")
async def get_community(_, info, slug):
	with local_session() as session:
		community = session.query(Community).filter(Community.slug == slug).first()
		if not community:
			return {"error": "invalid community id"}

	return community

@query.field("getCommunities")
async def get_communities(_, info):
	with local_session() as session:
		communities = session.query(Community)
	return communities

def community_subscribe(user, slug):
	CommunitySubscription.create(
		subscriber = user.slug, 
		community = slug
	)

def community_unsubscribe(user, slug):
	with local_session() as session:
		sub = session.query(CommunitySubscription).\
			filter(and_(CommunitySubscription.subscriber == user.slug, CommunitySubscription.community == slug)).\
			first()
		if not sub:
			raise Exception("subscription not exist")
		session.delete(sub)
		session.commit()

def get_subscribed_communities(user_slug):
	with local_session() as session:
		rows = session.query(Community.slug).\
			join(CommunitySubscription).\
			where(CommunitySubscription.subscriber == user_slug).\
			all()
	slugs = [row.slug for row in rows]
	return slugs
