from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.orm import local_session
from base.resolvers import query, mutation
from base.exceptions import ObjectNotExist, BaseHttpException
from orm.collab import Collab, CollabAuthor
from orm.shout import Shout
from orm.user import User


@query.field("getCollabs")
@login_required
async def get_collabs(_, info):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        collabs = session.query(Collab).filter(auth.user_id in Collab.authors)
        return collabs


@mutation.field("inviteCoauthor")
@login_required
async def invite_coauthor(_, info, author: str, shout: int):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        s = session.query(Shout).where(Shout.id == shout).one()
        if not s:
            raise ObjectNotExist("invalid shout id")
        else:
            c = session.query(Collab).where(Collab.shout == shout).one()
            if auth.user_id not in c.authors:
                raise BaseHttpException("you are not in authors list")
            else:
                invited_user = session.query(User).where(User.id == author).one()
                c.invites.append(invited_user)
                session.add(c)
                session.commit()

    # TODO: email notify
    return {}


@mutation.field("removeCoauthor")
@login_required
async def remove_coauthor(_, info, author: str, shout: int):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        s = session.query(Shout).where(Shout.id == shout).one()
        if not s:
            raise ObjectNotExist("invalid shout id")
        if auth.user_id != s.createdBy:
            raise BaseHttpException("only owner can remove coauthors")
        else:
            c = session.query(Collab).where(Collab.shout == shout).one()
            ca = session.query(CollabAuthor).join(User).where(c.shout == shout, User.slug == author).one()
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
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        s = session.query(Shout).where(Shout.id == shout).one()
        if not s:
            raise ObjectNotExist("invalid shout id")
        else:
            c = session.query(Collab).where(Collab.shout == shout).one()
            accepted = filter(lambda x: x.id == auth.user_id, c.invites).pop()
            if accepted:
                c.authors.append(accepted)
                s.authors.append(accepted)
                session.add(s)
                session.add(c)
                session.commit()
                return {}
            else:
                raise BaseHttpException("only invited can accept")
