from typing import List

from sqlalchemy import and_, desc

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import query
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import TopicFollower
from orm.user import AuthorFollower
from services.zine.shoutscache import prepare_shouts


@query.field("shoutsForFeed")
@login_required
async def get_user_feed(_, info, offset, limit) -> List[Shout]:
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
        topic_rows = (
            session.query(Shout)
            .join(ShoutTopic)
            .join(TopicFollower)
            .where(TopicFollower.follower == user.slug)
            .order_by(desc(Shout.createdAt))
        )
        shouts = shouts.union(topic_rows).limit(limit).offset(offset).all()
    return shouts


@query.field("recentCandidates")
@login_required
async def user_unpublished_shouts(_, info, offset, limit) -> List[Shout]:
    user = info.context["request"].user
    with local_session() as session:
        shouts = prepare_shouts(
            session.query(Shout)
            .join(ShoutAuthor)
            .where(and_(Shout.publishedAt.is_(None), ShoutAuthor.user == user.slug))
            .order_by(desc(Shout.createdAt))
            .limit(limit)
            .offset(offset)
            .all()
        )
        return shouts
