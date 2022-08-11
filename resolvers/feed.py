from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import query
from sqlalchemy import and_, desc
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import TopicFollower
from orm.user import AuthorFollower
from typing import List

@query.field("shoutsForFeed")
@login_required
def get_user_feed(_, info, page, size) -> List[Shout]:
	user = info.context["request"].user
	shouts = []
	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutAuthor).\
			join(AuthorFollower).\
			where(AuthorFollower.follower == user.slug).\
			order_by(desc(Shout.createdAt))
		topicrows = session.query(Shout).\
			join(ShoutTopic).\
			join(TopicFollower).\
			where(TopicFollower.follower == user.slug).\
			order_by(desc(Shout.createdAt))
		shouts = shouts.union(topicrows).limit(size).offset(page * size).all()
	return shouts

@query.field("myCandidates")
@login_required
async def user_unpublished_shouts(_, info, page = 1, size = 10) -> List[Shout]:
	user = info.context["request"].user
	shouts = []
	with local_session() as session:
		shouts = session.query(Shout).\
			join(ShoutAuthor).\
			where(and_(Shout.publishedAt == None, ShoutAuthor.user == user.slug)).\
			order_by(desc(Shout.createdAt)).\
			limit(size).\
			offset( page * size).\
			all()
	return shouts
