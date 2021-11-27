from orm import Topic, TopicSubscription
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from resolvers.zine import ShoutSubscriptions
from auth.authenticate import login_required
import asyncio


@query.field("topicsAll")
async def topics_all(_, info):
	topics = []
	with local_session() as session:
		topics = session.query(Topic)
	return topics

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
		author_shouts = session.query(Shout).filter(author in Shout.authors)
		# TODO: all the topics from author_shouts
		topics = []
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

@subscription.source("topicUpdated")
async def new_shout_generator(obj, info, user_id):
	try:
		with local_session() as session:
			topics = session.query(TopicSubscription.topic).filter(TopicSubscription.user == user_id).all()
		topics = set([item.topic for item in topics])
		shouts_queue = asyncio.Queue()
		await ShoutSubscriptions.register_subscription(shouts_queue)
		while True:
			shout = await shouts_queue.get()
			if topics.intersection(set(shout.topic_ids)):
				yield shout
	finally:
		await ShoutSubscriptions.del_subscription(shouts_queue)

@subscription.field("topicUpdated")
def shout_resolver(shout, info, user_id):
	return shout
