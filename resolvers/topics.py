from orm.topic import Topic, TopicFollower
from services.zine.topics import TopicStorage
from orm.shout import Shout
from orm.user import User
from services.stat.topicstat import TopicStat
from base.orm import local_session
from base.resolvers import mutation, query
from auth.authenticate import login_required
from sqlalchemy import and_
import random


@query.field("topicsAll")
async def topics_all(_, info):
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
async def topics_by_author(_, info, author):
    slugs = set()
    with local_session() as session:
        shouts = session.query(Shout).filter(Shout.authors.any(User.slug == author))
        for shout in shouts:
            slugs.update([topic.slug for topic in shout.topics])
    return await TopicStorage.get_topics(slugs)


@mutation.field("createTopic")
@login_required
async def create_topic(_, info, input):
    new_topic = Topic.create(**input)
    await TopicStorage.add_topic(new_topic)

    return {"topic": new_topic}


@mutation.field("updateTopic")
@login_required
async def update_topic(_, info, input):
    slug = input["slug"]

    session = local_session()
    topic = session.query(Topic).filter(Topic.slug == slug).first()

    if not topic:
        return {"error": "topic not found"}

    topic.update(input)
    session.commit()
    session.close()

    await TopicStorage.add_topic(topic)

    return {"topic": topic}


def topic_follow(user, slug):
    TopicFollower.create(follower=user.slug, topic=slug)


def topic_unfollow(user, slug):
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
        session.delete(sub)
        session.commit()


@query.field("topicsRandom")
async def topics_random(_, info, amount=12):
    topics = await TopicStorage.get_topics_all()
    normalized_topics = []
    for topic in topics:
        topic_stat = await TopicStat.get_stat(topic.slug)
        topic.stat = topic_stat
        if topic_stat["shouts"] > 2:
            normalized_topics.push(topic)
    return random.sample(normalized_topics, k=amount)
