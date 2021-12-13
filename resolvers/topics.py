from orm import Topic, TopicSubscription, TopicStorage, Shout, User
from orm.shout import TopicStat, ShoutAuthorStorage
from orm.user import UserStorage
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from resolvers.zine import ShoutSubscriptions
from auth.authenticate import login_required
import asyncio

@query.field("topicsBySlugs")
async def topics_by_slugs(_, info, slugs = None):
	with local_session() as session:
		topics = await TopicStorage.get_topics(slugs)
	all_fields = [node.name.value for node in info.field_nodes[0].selection_set.selections]
	if "topicStat" in all_fields:
		for topic in topics:
			topic.topicStat = await TopicStat.get_stat(topic.slug)
	return topics

@query.field("topicsByCommunity")
async def topics_by_community(_, info, community):
	with local_session() as session:
		return await TopicStorage.get_topics_by_community(community)

@query.field("topicsByAuthor")
async def topics_by_author(_, info, author):
	slugs = set()
	with local_session() as session:
		shouts = session.query(Shout).\
			filter(Shout.authors.any(User.slug == author))
		for shout in shouts:
			slugs.update([topic.slug for topic in shout.topics])
	return await TopicStorage.get_topics(slugs)

@query.field("getTopicAuthors")
async def topics_by_author(_, info, slug, count, page):
	shouts = await TopicStat.get_shouts(slug)
	authors = set()
	for shout in shouts:
		authors.update(await ShoutAuthorStorage.get_authors(shout))
	authors = list(authors)
	authors.sort() #TODO sort by username
	authors = authors[count * page : count * (page + 1) ]
	return [await UserStorage.get_user(author) for author in authors]

@mutation.field("createTopic")
@login_required
async def create_topic(_, info, input):
	new_topic = Topic.create(**input)
	await TopicStorage.add_topic(new_topic)

	return { "topic" : new_topic }

@mutation.field("updateTopic")
@login_required
async def update_topic(_, info, input):
	slug = input["slug"]

	session = local_session()
	topic = session.query(Topic).filter(Topic.slug == slug).first()

	if not topic:
		return { "error" : "topic not found" }

	topic.update(input)
	session.commit()
	session.close()

	await TopicStorage.add_topic(topic)

	return { "topic" : topic }

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
			if topics.intersection(set(shout.topic_slugs)):
				yield shout
	finally:
		await ShoutSubscriptions.del_subscription(shouts_queue)

@subscription.field("topicUpdated")
def shout_resolver(shout, info, user_id):
	return shout
