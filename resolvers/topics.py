from orm import Topic, TopicSubscription
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio

@query.field("topicsBySlugs")
async def topics_by_slugs(_, info, slugs):
	topics = []
	with local_session() as session:
		topics = session.query(Topic).filter(Topic.slug in slugs)
	return topics

@query.field("topicsByCommunity")
async def topics_by_community(_, info, community):
	topics = []
	with local_session() as session:
		topics = session.query(Topic).filter(Topic.community == community)
	return topics

@query.field("topicsByAuthor")
async def topics_by_author(_, info, author):
	topics = []
	with local_session() as session:
		topics = session.query(Topic).filter(Topic.community == community)
		return topics

@mutation.field("topicSubscribe")
@login_required
async def topic_subscribe(_, info, slug):
	auth = info.context["request"].auth
	user_id = auth.user_id
	sub = TopicSubscription.create({ user: user_id, topic: slug })
	return {} # type Result

@mutation.field("topicUnsubscribe")
@login_required
async def topic_unsubscribe(_, info, slug):
	auth = info.context["request"].auth
	user_id = auth.user_id
	sub = session.query(TopicSubscription).filter(TopicSubscription.user == user_id and TopicSubscription.topic == slug).first()
	with local_session() as session:
		session.delete(sub)
		return {} # type Result
	return { "error": "session error" }
