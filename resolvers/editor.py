from orm import Shout, ShoutRating, ShoutRatingStorage
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from resolvers.comments import comments_subscribe
from auth.authenticate import login_required
import asyncio
from datetime import datetime


@mutation.field("createShout")
@login_required
async def create_shout(_, info, input):
	user = info.context["request"].user

	topic_slugs = input.get("topic_slugs", [])
	if topic_slugs:
		del input["topic_slugs"]

	new_shout = Shout.create(**input)
	ShoutAuthor.create(
		shout = new_shout.slug,
		user = user.slug)

	comments_subscribe(user, new_shout.slug, True)

	if "mainTopic" in input:
		topic_slugs.append(input["mainTopic"])

	for slug in topic_slugs:
		topic = ShoutTopic.create(
			shout = new_shout.slug,
			topic = slug)
	new_shout.topic_slugs = topic_slugs

	task = GitTask(
		input,
		user.username,
		user.email,
		"new shout %s" % (new_shout.slug)
		)
		
	await ShoutCommentsStorage.send_shout(new_shout)

	return {
		"shout" : new_shout
	}

@mutation.field("updateShout")
@login_required
async def update_shout(_, info, input):
	auth = info.context["request"].auth
	user_id = auth.user_id

	slug = input["slug"]

	session = local_session()
	user = session.query(User).filter(User.id == user_id).first()
	shout = session.query(Shout).filter(Shout.slug == slug).first()

	if not shout:
		return {
			"error" : "shout not found"
		}

	authors = [author.id for author in shout.authors]
	if not user_id in authors:
		scopes = auth.scopes
		print(scopes)
		if not Resource.shout_id in scopes:
			return {
				"error" : "access denied"
			}

	shout.update(input)
	shout.updatedAt = datetime.now()
	session.commit()
	session.close()

	for topic in input.get("topic_slugs", []):
		ShoutTopic.create(
			shout = slug,
			topic = topic)

	task = GitTask(
		input,
		user.username,
		user.email,
		"update shout %s" % (slug)
		)

	return {
		"shout" : shout
	}

@mutation.field("deleteShout")
@login_required
async def delete_shout(_, info, slug):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		shout = session.query(Shout).filter(Shout.slug == slug).first()
		authors = [author.id for author in shout.authors]
		if not comment:
			return {"error": "invalid shout slug"}
		if user_id not in authors:
			return {"error": "access denied"}

		shout.deletedAt = datetime.now()
		session.commit()

	return {}
