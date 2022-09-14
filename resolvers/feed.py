from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import query
from sqlalchemy import and_, desc
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import TopicFollower
from orm.user import AuthorFollower
from typing import List
from services.zine.shoutscache import prepare_shouts


@query.field("shoutsForFeed")
@login_required
def get_user_feed(_, info, offset, limit) -> List[Shout]:
    user = info.context["request"].user
    shouts = []
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutAuthor)
            .join(AuthorFollower)
            .where(AuthorFollower.follower == user.slug)
            .order_by(desc(Shout.createdAt))
        )
        topicrows = (
            session.query(Shout)
            .join(ShoutTopic)
            .join(TopicFollower)
            .where(TopicFollower.follower == user.slug)
            .order_by(desc(Shout.createdAt))
        )
        shouts = shouts.union(topicrows).limit(limit).offset(offset).all()
    return shouts


@query.field("myCandidates")
@login_required
async def user_unpublished_shouts(_, info, offset, limit) -> List[Shout]:
    user = info.context["request"].user
    shouts = []
    with local_session() as session:
        shouts = prepare_shouts(
            session.query(Shout)
            .join(ShoutAuthor)
            .where(and_(not bool(Shout.publishedAt), ShoutAuthor.user == user.slug))
            .order_by(desc(Shout.createdAt))
            .limit(limit)
            .offset(offset)
            .all()
        )
    return shouts
