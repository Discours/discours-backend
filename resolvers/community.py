from orm import Community, CommunitySubscription
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio
from datetime import datetime

from sqlalchemy import and_

@mutation.field("createCommunity")
@login_required
async def create_community(_, info, title, desc):
	auth = info.context["request"].auth
	user_id = auth.user_id

	community = Community.create(
		title = title,
		desc = desc
		)

	return {"community": community}

@mutation.field("updateCommunity")
@login_required
async def update_community(_, info, id, title, desc, pic):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		community = session.query(Community).filter(Community.id == id).first()
		if not community:
			return {"error": "invalid community id"}
		if community.owner != user_id:
			return {"error": "access denied"}
		community.title = title
		community.desc = desc
		community.pic = pic
		community.updatedAt = datetime.now()
		
		session.commit()

@mutation.field("deleteCommunity")
@login_required
async def delete_community(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		community = session.query(Community).filter(Community.id == id).first()
		if not community:
			return {"error": "invalid community id"}
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
