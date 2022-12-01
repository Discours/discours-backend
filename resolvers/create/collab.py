from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import query, mutation
from base.exceptions import ObjectNotExist, BaseHttpException
from orm.collab import Collab, CollabAuthor
from orm.shout import Shout
from orm.user import User


@query.field("getCollabs")
@login_required
async def get_collabs(_, info):
    user = info.context["request"].user
    with local_session() as session:
        collabs = session.query(Collab).filter(user.slug in Collab.authors)
        return collabs


@mutation.field("inviteCoauthor")
@login_required
async def invite_coauthor(_, info, author: str, shout: int):
    user = info.context["request"].user
    with local_session() as session:
        s = session.query(Shout).where(Shout.id == shout).one()
        if not s:
            raise ObjectNotExist("invalid shout id")
        else:
            c = session.query(Collab).where(Collab.shout == shout).one()
            if user.slug not in c.authors:
                raise BaseHttpException("you are not in authors list")
            else:
                invited_user = session.query(User).where(User.slug == author).one()
                c.invites.append(invited_user)
                session.add(c)
                session.commit()

    # TODO: email notify
    return {}


@mutation.field("removeCoauthor")
@login_required
async def remove_coauthor(_, info, author: str, shout: int):
    user = info.context["request"].user
    with local_session() as session:
        s = session.query(Shout).where(Shout.id == shout).one()
        if not s:
            raise ObjectNotExist("invalid shout id")
        if user.slug != s.createdBy.slug:
            raise BaseHttpException("only onwer can remove coauthors")
        else:
            c = session.query(Collab).where(Collab.shout == shout).one()
            ca = session.query(CollabAuthor).where(c.shout == shout, c.author == author).one()
            session.remve(ca)
            c.invites = filter(lambda x: x.slug == author, c.invites)
            c.authors = filter(lambda x: x.slug == author, c.authors)
            session.add(c)
            session.commit()

    # TODO: email notify
    return {}


@mutation.field("acceptCoauthor")
@login_required
async def accept_coauthor(_, info, shout: int):
    user = info.context["request"].user
    with local_session() as session:
        s = session.query(Shout).where(Shout.id == shout).one()
        if not s:
            raise ObjectNotExist("invalid shout id")
        else:
            c = session.query(Collab).where(Collab.shout == shout).one()
            accepted = filter(lambda x: x.slug == user.slug, c.invites).pop()
            if accepted:
                c.authors.append(accepted)
                s.authors.append(accepted)
                session.add(s)
                session.add(c)
                session.commit()
                return {}
            else:
                raise BaseHttpException("only invited can accept")
