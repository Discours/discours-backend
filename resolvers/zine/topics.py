from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import aliased

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm import User
from orm.shout import ShoutAuthor, ShoutTopic
from orm.topic import Topic, TopicFollower


def add_topic_stat_columns(q):
    aliased_shout_author = aliased(ShoutAuthor)
    aliased_topic_follower = aliased(TopicFollower)

    q = (
        q.outerjoin(ShoutTopic, Topic.id == ShoutTopic.topic)
        .add_columns(func.count(distinct(ShoutTopic.shout)).label('shouts_stat'))
        .outerjoin(aliased_shout_author, ShoutTopic.shout == aliased_shout_author.shout)
        .add_columns(func.count(distinct(aliased_shout_author.user)).label('authors_stat'))
        .outerjoin(aliased_topic_follower)
        .add_columns(func.count(distinct(aliased_topic_follower.follower)).label('followers_stat'))
    )

    q = q.group_by(Topic.id)

    return q


def add_stat(topic, stat_columns):
    [shouts_stat, authors_stat, followers_stat] = stat_columns
    topic.stat = {"shouts": shouts_stat, "authors": authors_stat, "followers": followers_stat}

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
    try:
        with local_session() as session:
            topic = session.query(Topic).where(Topic.slug == slug).one()

            following = TopicFollower.create(topic=topic.id, follower=user_id)
            session.add(following)
            session.commit()
            return True
    except:
        return False


def topic_unfollow(user_id, slug):
    try:
        with local_session() as session:
            sub = (
                session.query(TopicFollower)
                .join(Topic)
                .filter(and_(TopicFollower.follower == user_id, Topic.slug == slug))
                .first()
            )
            if sub:
                session.delete(sub)
                session.commit()
                return True
    except:
        pass
    return False


@query.field("topicsRandom")
async def topics_random(_, info, amount=12):
    q = select(Topic)
    q = q.join(ShoutTopic)
    q = q.group_by(Topic.id)
    q = q.having(func.count(distinct(ShoutTopic.shout)) > 2)
    q = q.order_by(func.random()).limit(amount)

    topics = []
    with local_session() as session:
        for [topic] in session.execute(q):
            topics.append(topic)

    return topics
