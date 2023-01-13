from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.orm import local_session
from base.resolvers import query, mutation
from base.exceptions import ObjectNotExist, BaseHttpException
from orm.draft import DraftCollab, CollabAuthor
from orm.shout import Shout
from orm.user import User


# TODO: use updatedAt


@query.field("loadDrafts")
@login_required
async def get_drafts(_, info):
    auth: AuthCredentials = info.context["request"].auth
    drafts = []
    with local_session() as session:
        drafts = session.query(DraftCollab).filter(auth.user_id in DraftCollab.authors)
    return {
        "drafts": drafts
    }


@mutation.field("createDraft") # TODO
@login_required
async def create_draft(_, info):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
    pass


@mutation.field("deleteDraft") # TODO
@login_required
async def delete_draft(_, info, draft: int = 0):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
    pass

@mutation.field("updateDraft") # TODO
@login_required
async def update_draft(_, info, author: int = 0, draft: int = 0):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        s = session.query(DraftCollab).where(DraftCollab.id == draft).one()  # raises Error when not found
        if auth.user_id not in s.authors:
            # raise BaseHttpException("only owner can remove coauthors")
            return {
                "error": "Only authors can update draft"
            }
        elif not s:
            return {
                "error": "There is no draft with this id"
            }
        else:
            c = session.query(DraftCollab).where(DraftCollab.id == draft).one()
            ca = session.query(CollabAuthor).join(User).where(c.id == draft).filter(User.id == author).one()
            session.remve(ca)
            c.invites = filter(lambda x: x.id == author, c.invites)
            c.authors = filter(lambda x: x.id == author, c.authors)
            session.add(c)
            session.commit()

    # TODO: email notify
    return {}

@mutation.field("inviteAuthor")
@login_required
async def invite_coauthor(_, info, author: int = 0, draft: int = 0):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        c = session.query(DraftCollab).where(DraftCollab.id == draft).one()
        if auth.user_id not in c.authors:
            # raise BaseHttpException("you are not in authors list")
            return {
                "error": "You are not in authors list"
            }
        else:
            invited_user = session.query(User).where(User.id == author).one()
            c.invites.append(invited_user)
            session.add(c)
            session.commit()

    # TODO: email notify
    return {}


@mutation.field("inviteAccept")
@login_required
async def accept_coauthor(_, info, draft: int):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        c = session.query(DraftCollab).where(DraftCollab.id == draft).one()
        accepted = filter(lambda x: x.id == auth.user_id, c.invites).pop()
        if accepted:
            c.authors.append(accepted)
            session.add(c)
            session.commit()
            return {}
        else:
            # raise BaseHttpException("only invited can accept")
            return {
                "error": "You don't have an invitation yet"
            }
