from datetime import datetime
from base.orm import local_session
from orm.collab import Collab
from orm.shout import Shout
from orm.user import User
from base.resolvers import query, mutation
from auth.authenticate import login_required


@query.field("getCollabs")
@login_required
async def get_collabs(_, info):
    auth = info.context["request"].auth
    user_id = auth.user_id
    collabs = []
    with local_session() as session:
        user = session.query(User).where(User.id == user_id).first()
        collabs = session.query(Collab).filter(user.slug in Collab.authors)
    return collabs


@mutation.field("inviteAuthor")
@login_required
async def invite_author(_, info, author, shout):
    auth = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        shout = session.query(Shout).filter(Shout.slug == shout).first()
        if not shout:
            return {"error": "invalid shout slug"}
        authors = [a.id for a in shout.authors]
        if user_id not in authors:
            return {"error": "access denied"}
        author = session.query(User).filter(User.slug == author).first()
        if author.id in authors:
            return {"error": "already added"}
        shout.authors.append(author)
        shout.updated_at = datetime.now()
        shout.save()
        session.commit()

    # TODO: email notify

    return {}


@mutation.field("removeAuthor")
@login_required
async def remove_author(_, info, author, shout):
    auth = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        shout = session.query(Shout).filter(Shout.slug == shout).first()
        if not shout:
            return {"error": "invalid shout slug"}
        authors = [author.id for author in shout.authors]
        if user_id not in authors:
            return {"error": "access denied"}
        author = session.query(User).filter(User.slug == author).first()
        if author.id not in authors:
            return {"error": "not in authors"}
        shout.authors.remove(author)
        shout.updated_at = datetime.now()
        shout.save()
        session.commit()

    # result = Result("INVITED")
    # FIXME: await ShoutStorage.put(result)

    # TODO: email notify

    return {}
