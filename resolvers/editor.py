from datetime import datetime

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation
from orm import Shout
from orm.rbac import Resource
from orm.shout import ShoutAuthor, ShoutTopic
from orm.user import User
from resolvers.reactions import reactions_follow, reactions_unfollow
from services.zine.gittask import GitTask


@mutation.field("createShout")
@login_required
async def create_shout(_, info, inp):
    user = info.context["request"].user

    topic_slugs = inp.get("topic_slugs", [])
    if topic_slugs:
        del inp["topic_slugs"]

    new_shout = Shout.create(**inp)
    ShoutAuthor.create(shout=new_shout.slug, user=user.slug)

    reactions_follow(user, new_shout.slug, True)

    if "mainTopic" in inp:
        topic_slugs.append(inp["mainTopic"])

    for slug in topic_slugs:
        ShoutTopic.create(shout=new_shout.slug, topic=slug)
    new_shout.topic_slugs = topic_slugs

    GitTask(inp, user.username, user.email, "new shout %s" % (new_shout.slug))

    # await ShoutCommentsStorage.send_shout(new_shout)

    return {"shout": new_shout}


@mutation.field("updateShout")
@login_required
async def update_shout(_, info, inp):
    auth = info.context["request"].auth
    user_id = auth.user_id

    slug = inp["slug"]

    session = local_session()
    user = session.query(User).filter(User.id == user_id).first()
    shout = session.query(Shout).filter(Shout.slug == slug).first()

    if not shout:
        return {"error": "shout not found"}

    authors = [author.id for author in shout.authors]
    if user_id not in authors:
        scopes = auth.scopes
        print(scopes)
        if Resource.shout_id not in scopes:
            return {"error": "access denied"}

    shout.update(inp)
    shout.updatedAt = datetime.now()
    session.add(shout)
    session.commit()
    session.close()

    for topic in inp.get("topic_slugs", []):
        ShoutTopic.create(shout=slug, topic=topic)

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
        shout.deletedAt = datetime.now()
        session.add(shout)
        session.commit()

    return {}
