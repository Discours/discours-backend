from orm.community import Community, CommunityFollower
from orm.base import local_session
from orm.user import User
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
	community_slug = input.get('slug', '')

	with local_session() as session:
		owner = session.query(User).filter(User.id == user_id) # note list here
		community = session.query(Community).filter(Community.slug == community_slug).first()
		editors = [e.slug for e in community.editors]
		if not community:
			return {"error": "invalid community id"}
		if community.createdBy not in (owner + editors):
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

def community_follow(user, slug):
	CommunityFollower.create(
		follower = user.slug, 
		community = slug
	)

def community_unfollow(user, slug):
	with local_session() as session:
		following = session.query(CommunityFollower).\
			filter(and_(CommunityFollower.follower == user.slug, CommunityFollower.community == slug)).\
			first()
		if not following:
			raise Exception("[orm.community] following was not exist")
		session.delete(following)
		session.commit()

@query.field("userFollowedCommunities")
def get_followed_communities(_, user_slug) -> list[Community]:
	ccc = []
	with local_session() as session:
		ccc = session.query(Community.slug).\
			join(CommunityFollower).\
			where(CommunityFollower.follower == user_slug).\
			all()
	return ccc
