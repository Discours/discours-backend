from orm.topic import Topic, TopicFollower
from services.zine.topics import TopicStorage
from services.stat.topicstat import TopicStat
from base.orm import local_session
from base.resolvers import mutation, query
from auth.authenticate import login_required
from sqlalchemy import and_
import random
from services.zine.shoutscache import ShoutsCache


@query.field("topicsAll")
async def topics_all(_, _info):
    topics = await TopicStorage.get_topics_all()
    for topic in topics:
        topic.stat = await TopicStat.get_stat(topic.slug)
    return topics


@query.field("topicsByCommunity")
async def topics_by_community(_, info, community):
    topics = await TopicStorage.get_topics_by_community(community)
    for topic in topics:
        topic.stat = await TopicStat.get_stat(topic.slug)
    return topics


@query.field("topicsByAuthor")
async def topics_by_author(_, _info, author):
    topics = ShoutsCache.by_author.get(author)
    author_topics = set()
    for tpc in topics:
        tpc = await TopicStorage.topics[tpc.slug]
        tpc.stat = await TopicStat.get_stat(tpc.slug)
        author_topics.add(tpc)
    return list(author_topics)


@mutation.field("createTopic")
@login_required
async def create_topic(_, _info, inp):
    new_topic = Topic.create(**inp)
    await TopicStorage.update_topic(new_topic)
    return {"topic": new_topic}


@mutation.field("updateTopic")
@login_required
async def update_topic(_, _info, inp):
    slug = inp["slug"]
    session = local_session()
    topic = session.query(Topic).filter(Topic.slug == slug).first()
    if not topic:
        return {"error": "topic not found"}
    topic.update(**inp)
    session.commit()
    session.close()
    await TopicStorage.update_topic(topic.slug)
    return {"topic": topic}


async def topic_follow(user, slug):
    TopicFollower.create(follower=user.slug, topic=slug)
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
    topics = await TopicStorage.get_topics_all()
    normalized_topics = []
    for topic in topics:
        topic_stat = await TopicStat.get_stat(topic.slug)
        # FIXME: expects topicstat fix
        # #if topic_stat["shouts"] > 2:
        #    normalized_topics.append(topic)
        topic.stat = topic_stat
        normalized_topics.append(topic)
    sample_length = min(len(normalized_topics), amount)
    return random.sample(normalized_topics, sample_length)
