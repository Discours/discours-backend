import sqlalchemy as sa
from sqlalchemy import and_, select
from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm import Shout
from orm.topic import Topic, TopicFollower
# from services.stat.reacted import ReactedStorage


# from services.stat.viewed import ViewedStorage


async def get_topic_stat(slug):
    return {
        "shouts": len(TopicStat.shouts_by_topic.get(slug, {}).keys()),
        "authors": len(TopicStat.authors_by_topic.get(slug, {}).keys()),
        "followers": len(TopicStat.followers_by_topic.get(slug, {}).keys()),
        # "viewed": await ViewedStorage.get_topic(slug),
        # "reacted": len(await ReactedStorage.get_topic(slug)),
        # "commented": len(await ReactedStorage.get_topic_comments(slug)),
        # "rating": await ReactedStorage.get_topic_rating(slug)
    }


@query.field("topicsAll")
async def topics_all(_, _info):
    topics = await TopicStorage.get_topics_all()
    for topic in topics:
        topic.stat = await get_topic_stat(topic.slug)
    return topics


@query.field("topicsByCommunity")
async def topics_by_community(_, info, community):
    topics = await TopicStorage.get_topics_by_community(community)
    for topic in topics:
        topic.stat = await get_topic_stat(topic.slug)
    return topics


@query.field("topicsByAuthor")
async def topics_by_author(_, _info, author):
    shouts = TopicStorage.get_topics_by_author(author)
    author_topics = set()
    for s in shouts:
        for tpc in s.topics:
            tpc = await TopicStorage.topics[tpc.slug]
            tpc.stat = await get_topic_stat(tpc.slug)
            author_topics.add(tpc)
    return list(author_topics)


@query.field("getTopic")
async def get_topic(_, _info, slug):
    t = TopicStorage.topics[slug]
    t.stat = await get_topic_stat(slug)
    return t


@mutation.field("createTopic")
@login_required
async def create_topic(_, _info, inp):
    with local_session() as session:
        # TODO: check user permissions to create topic for exact community
        new_topic = Topic.create(**inp)
        session.add(new_topic)
        session.commit()
    await TopicStorage.update_topic(new_topic)
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
            await TopicStorage.update_topic(topic.slug)
            return {"topic": topic}


async def topic_follow(user, slug):
    with local_session() as session:
        following = TopicFollower.create(topic=slug, follower=user.slug)
        session.add(following)
        session.commit()
        await TopicStorage.update_topic(slug)


async def topic_unfollow(user, slug):
    with local_session() as session:
        sub = (
            session.query(TopicFollower)
                .filter(
                and_(TopicFollower.follower == user.slug, TopicFollower.topic == slug)
            )
                .first()
        )
        if not sub:
            raise Exception("[resolvers.topics] follower not exist")
        else:
            session.delete(sub)
        session.commit()
    await TopicStorage.update_topic(slug)


@query.field("topicsRandom")
async def topics_random(_, info, amount=12):
    with local_session() as session:
        q = select(Topic).join(Shout).group_by(Topic.id).having(sa.func.count(Shout.id) > 2).order_by(
            sa.func.random()).limit(amount)
        random_topics = list(map(lambda result_item: result_item.Topic, session.execute(q)))
        return random_topics
