from sqlalchemy import and_, select, distinct, func
from sqlalchemy.orm import aliased

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.shout import ShoutTopic, ShoutAuthor
from orm.topic import Topic, TopicFollower
from orm import Shout, User


def add_topic_stat_columns(q):
    aliased_shout_topic = aliased(ShoutTopic)
    aliased_shout_author = aliased(ShoutAuthor)
    aliased_topic_follower = aliased(TopicFollower)

    q = q.outerjoin(aliased_shout_topic, Topic.id == aliased_shout_topic.topic).add_columns(
        func.count(distinct(aliased_shout_topic.shout)).label('shouts_stat')
    ).outerjoin(aliased_shout_author, aliased_shout_topic.shout == aliased_shout_author.shout).add_columns(
        func.count(distinct(aliased_shout_author.user)).label('authors_stat')
    ).outerjoin(aliased_topic_follower,
                and_(
                    aliased_topic_follower.topic == Topic.id,
                    aliased_topic_follower.follower == aliased_shout_author.id
                )).add_columns(
        func.count(distinct(aliased_topic_follower.follower)).label('followers_stat')
    )

    q = q.group_by(Topic.id)

    return q


def add_stat(topic, stat_columns):
    [shouts_stat, authors_stat, followers_stat] = stat_columns
    topic.stat = {
        "shouts": shouts_stat,
        "authors": authors_stat,
        "followers": followers_stat
    }

    return topic


def get_topics_from_query(q):
    topics = []
    with local_session() as session:
        for [topic, *stat_columns] in session.execute(q):
            topic = add_stat(topic, stat_columns)
            topics.append(topic)

    return topics


def followed_by_user(user_id):
    q = select(Topic)
    q = add_topic_stat_columns(q)
    q = q.join(TopicFollower).where(TopicFollower.follower == user_id)

    return get_topics_from_query(q)


@query.field("topicsAll")
async def topics_all(_, _info):
    q = select(Topic)
    q = add_topic_stat_columns(q)

    return get_topics_from_query(q)


@query.field("topicsByCommunity")
async def topics_by_community(_, info, community):
    q = select(Topic).where(Topic.community == community)
    q = add_topic_stat_columns(q)

    return get_topics_from_query(q)


@query.field("topicsByAuthor")
async def topics_by_author(_, _info, author):
    q = select(Topic)
    q = add_topic_stat_columns(q)
    q = q.join(User).where(User.slug == author)

    return get_topics_from_query(q)


@query.field("getTopic")
async def get_topic(_, _info, slug):
    q = select(Topic).where(Topic.slug == slug)
    q = add_topic_stat_columns(q)

    topics = get_topics_from_query(q)
    return topics[0]


@mutation.field("createTopic")
@login_required
async def create_topic(_, _info, inp):
    with local_session() as session:
        # TODO: check user permissions to create topic for exact community
        new_topic = Topic.create(**inp)
        session.add(new_topic)
        session.commit()

    return {"topic": new_topic}


@mutation.field("updateTopic")
@login_required
async def update_topic(_, _info, inp):
    slug = inp["slug"]
    with local_session() as session:
        topic = session.query(Topic).filter(Topic.slug == slug).first()
        if not topic:
            return {"error": "topic not found"}
        else:
            topic.update(**inp)
            session.commit()

            return {"topic": topic}


def topic_follow(user_id, slug):
    with local_session() as session:
        topic = session.query(Topic).where(Topic.slug == slug).one()

        following = TopicFollower.create(topic=topic.id, follower=user_id)
        session.add(following)
        session.commit()


def topic_unfollow(user_id, slug):
    with local_session() as session:
        sub = (
            session.query(TopicFollower).join(Topic).filter(
                and_(
                    TopicFollower.follower == user_id,
                    Topic.slug == slug
                )
            ).first()
        )
        if not sub:
            raise Exception("[resolvers.topics] follower not exist")
        else:
            session.delete(sub)
        session.commit()


@query.field("topicsRandom")
async def topics_random(_, info, amount=12):
    q = select(Topic)
    q = add_topic_stat_columns(q)
    q = q.join(ShoutTopic).join(Shout, ShoutTopic.shout == Shout.id).group_by(Topic.id).having(func.count(Shout.id) > 2)
    q = q.order_by(func.random()).limit(amount)

    return get_topics_from_query(q)
