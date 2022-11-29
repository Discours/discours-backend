from datetime import datetime, timezone

from sqlalchemy import and_

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation
from orm.rbac import Resource
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import TopicFollower, Topic
from orm.user import User
from resolvers.zine.reactions import reactions_follow, reactions_unfollow
from services.zine.gittask import GitTask


@mutation.field("createShout")
@login_required
async def create_shout(_, info, inp):
    user = info.context["request"].user

    topic_slugs = inp.get("topic_slugs", [])
    if topic_slugs:
        del inp["topic_slugs"]

    with local_session() as session:
        new_shout = Shout.create(**inp)

        # NOTE: shout made by one first author
        sa = ShoutAuthor.create(shoutId=new_shout.id, userId=user.id)
        session.add(sa)

        reactions_follow(user, new_shout.slug, True)

        if "mainTopic" in inp:
            topic_slugs.append(inp["mainTopic"])

        for slug in topic_slugs:
            topic = session.query(Topic).where(Topic.slug == slug).one()

            st = ShoutTopic.create(shoutId=new_shout.id, topicId=topic.id)
            session.add(st)
            tf = session.query(TopicFollower).where(
                and_(TopicFollower.followerId == user.id, TopicFollower.topicId == topic.id)
            )

            if not tf:
                tf = TopicFollower.create(followerId=user.id, topicId=topic.id, auto=True)
                session.add(tf)

        new_shout.topic_slugs = topic_slugs
        session.add(new_shout)

        session.commit()

    GitTask(inp, user.username, user.email, "new shout %s" % new_shout.slug)

    return {"shout": new_shout}


@mutation.field("updateShout")
@login_required
async def update_shout(_, info, inp):
    auth = info.context["request"].auth
    user_id = auth.user_id
    slug = inp["slug"]

    with local_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        shout = session.query(Shout).filter(Shout.slug == slug).first()
        if not shout:
            return {"error": "shout not found"}

        authors = [author.id for author in shout.authors]
        if user_id not in authors:
            scopes = auth.scopes
            print(scopes)
            if Resource.shoutId not in scopes:
                return {"error": "access denied"}
        else:
            shout.update(inp)
            shout.updatedAt = datetime.now(tz=timezone.utc)
            session.add(shout)
            if inp.get("topics"):
                # remove old links
                links = session.query(ShoutTopic).where(ShoutTopic.shoutId == shout.id).all()
                for topiclink in links:
                    session.delete(topiclink)
                # add new topic links
                for topic in inp.get("topics", []):
                    ShoutTopic.create(shout=slug, topic=topic)
            session.commit()

    GitTask(inp, user.username, user.email, "update shout %s" % (slug))

    return {"shout": shout}


@mutation.field("deleteShout")
@login_required
async def delete_shout(_, info, slug):
    auth = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        shout = session.query(Shout).filter(Shout.slug == slug).first()
        authors = [a.id for a in shout.authors]
        if not shout:
            return {"error": "invalid shout slug"}
        if user_id not in authors:
            return {"error": "access denied"}
        for a in authors:
            reactions_unfollow(a.slug, slug, True)
        shout.deletedAt = datetime.now(tz=timezone.utc)
        session.add(shout)
        session.commit()

    return {}
