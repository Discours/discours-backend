from datetime import datetime, timezone

from sqlalchemy import and_

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.orm import local_session
from base.resolvers import mutation
from orm.rbac import Resource
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import TopicFollower, Topic
from orm.user import User
from resolvers.zine.reactions import reactions_follow, reactions_unfollow
from services.zine.gittask import GitTask
# from resolvers.inbox.chats import create_chat
# from services.inbox.storage import MessagesStorage


@mutation.field("createShout")
@login_required
async def create_shout(_, info, inp):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        topics = session.query(Topic).filter(Topic.slug.in_(inp.get('topics', []))).all()

        new_shout = Shout.create(**{
            "title": inp.get("title"),
            "subtitle": inp.get('subtitle'),
            "body": inp.get("body", ''),
            "authors": inp.get("authors", []),
            "slug": inp.get("slug"),
            "mainTopic": inp.get("mainTopic"),
            "visibility": "owner",
            "createdBy": auth.user_id
        })

        for topic in topics:
            t = ShoutTopic.create(topic=topic.id, shout=new_shout.id)
            session.add(t)

        # if auth.user_id in authors:
        #     authors.remove(auth.user_id)
        # Chat room code, uncomment it
        # if authors:
        #     chat = create_chat(None, info, new_shout.title, members=authors)
        #     # create a cooperative chatroom
        #     await MessagesStorage.register_chat(chat)
        #     # now we should create a collab
        #     new_collab = Collab.create({
        #         "shout": new_shout.id,
        #         "authors": [auth.user_id, ],
        #         "invites": authors
        #     })
        #     session.add(new_collab)

        # NOTE: shout made by one first author
        sa = ShoutAuthor.create(shout=new_shout.id, user=auth.user_id)
        session.add(sa)

        # if "mainTopic" in inp:
        #     new_shout.topics.append(inp["mainTopic"])

        session.add(new_shout)

        reactions_follow(auth.user_id, new_shout.id, True)

        # for slug in new_shout.topics:
        #     topic = session.query(Topic).where(Topic.slug == slug).one()
        #
        #     st = ShoutTopic.create(shout=new_shout.id, topic=topic.id)
        #     session.add(st)
        #
        #     tf = session.query(TopicFollower).where(
        #         and_(TopicFollower.follower == auth.user_id, TopicFollower.topic == topic.id)
        #     )
        #
        #     if not tf:
        #         tf = TopicFollower.create(follower=auth.user_id, topic=topic.id, auto=True)
        #         session.add(tf)

        session.commit()

        # TODO
        # GitTask(inp, user.username, user.email, "new shout %s" % new_shout.slug)

        if new_shout.slug is None:
            new_shout.slug = f"draft-{new_shout.id}"
            session.commit()

    return {"shout": new_shout}


@mutation.field("updateShout")
@login_required
async def update_shout(_, info, shout_id, shout_input):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        shout = session.query(Shout).filter(Shout.id == shout_id).first()

        if not shout:
            return {"error": "shout not found"}

        authors = [author.id for author in shout.authors]
        if auth.user_id not in authors:
            scopes = auth.scopes
            print(scopes)
            if Resource.shout not in scopes:
                return {"error": "access denied"}
        else:
            shout.update(shout_input)
            shout.updatedAt = datetime.now(tz=timezone.utc)

            if shout_input.get("topics"):
                # remove old links
                links = session.query(ShoutTopic).where(ShoutTopic.shout == shout.id).all()
                for topiclink in links:
                    session.delete(topiclink)
                # add new topic links
                # for topic_slug in inp.get("topics", []):
                #     topic = session.query(Topic).filter(Topic.slug == topic_slug).first()
                #     shout_topic = ShoutTopic.create(shout=shout.id, topic=topic.id)
                #     session.add(shout_topic)
            session.commit()
    # GitTask(inp, user.username, user.email, "update shout %s" % slug)

    return {"shout": shout}


@mutation.field("publishShout")
@login_required
async def publish_shout(_, info, slug, inp):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        shout = session.query(Shout).filter(Shout.slug == slug).first()
        if not shout:
            return {"error": "shout not found"}

        else:
            shout.update(inp)
            shout.visibility = "community"
            shout.updatedAt = datetime.now(tz=timezone.utc)
            session.commit()

    return {"shout": shout}


@mutation.field("deleteShout")
@login_required
async def delete_shout(_, info, slug):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        shout = session.query(Shout).filter(Shout.slug == slug).first()
        authors = [a.id for a in shout.authors]
        if not shout:
            return {"error": "invalid shout slug"}
        if auth.user_id not in authors:
            return {"error": "access denied"}
        for a in authors:
            reactions_unfollow(a.id, slug)
        shout.deletedAt = datetime.now(tz=timezone.utc)
        session.add(shout)
        session.commit()

    return {}
