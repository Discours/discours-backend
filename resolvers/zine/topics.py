from sqlalchemy import and_, select, distinct, func
from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.shout import ShoutTopic, ShoutAuthor
from orm.topic import Topic, TopicFollower
from orm import Shout, User


def add_topic_stat_columns(q):
    q = q.outerjoin(ShoutTopic, Topic.id == ShoutTopic.topicId).add_columns(
        func.count(distinct(ShoutTopic.shoutId)).label('shouts_stat')
    ).outerjoin(ShoutAuthor, ShoutTopic.shoutId == ShoutAuthor.shoutId).add_columns(
        func.count(distinct(ShoutAuthor.userId)).label('authors_stat')
    ).outerjoin(TopicFollower,
                and_(
                    TopicFollower.topicId == Topic.id,
                    TopicFollower.followerId == ShoutAuthor.id
                )).add_columns(
        func.count(distinct(TopicFollower.followerId)).label('followers_stat')
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


def followed_by_user(user_slug):
    q = select(Topic)
    q = add_topic_stat_columns(q)
    q = q.join(User).where(User.slug == user_slug)

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


async def topic_follow(user, slug):
    with local_session() as session:
        topic = session.query(Topic).where(Topic.slug == slug).one()

        following = TopicFollower.create(topicId=topic.id, followerId=user.id)
        session.add(following)
        session.commit()


async def topic_unfollow(user, slug):
    with local_session() as session:
        sub = (
            session.query(TopicFollower).join(Topic).filter(
                and_(
                    TopicFollower.followerId == user.id,
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
    q = q.join(Shout, ShoutTopic.shoutId == Shout.id).group_by(Topic.id).having(func.count(Shout.id) > 2)
    q = q.order_by(func.random()).limit(amount)

    return get_topics_from_query(q)
