from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.orm import local_session
from base.resolvers import query, mutation
from orm.draft import DraftCollab, DraftAuthor
from orm.shout import Shout
from orm.topic import Topic
from orm.user import User
from datetime import datetime, timezone
from transliterate import translit
import re


@query.field("loadDrafts")
@login_required
async def load_drafts(_, info):
    auth: AuthCredentials = info.context["request"].auth
    drafts = []
    with local_session() as session:
        drafts = session.query(DraftCollab).filter(auth.user_id in DraftCollab.authors)
        return drafts


@mutation.field("createDraft")  # TODO
@login_required
async def create_draft(_, info, draft_input):
    auth: AuthCredentials = info.context["request"].auth
    draft_input['createdBy'] = auth.user_id
    with local_session() as session:
        collab = DraftCollab.create(**draft_input)
        session.add(collab)
        session.commit()

    # TODO: email notify to all authors
    return {}


@mutation.field("deleteDraft")
@login_required
async def delete_draft(_, info, draft: int = 0):
    auth: AuthCredentials = info.context["request"].auth
    with local_session() as session:
        d = session.query(DraftCollab).where(DraftCollab.id == draft).one()
        if auth.user_id not in d.authors:
            # raise BaseHttpException("only owner can remove coauthors")
            return {
                "error": "Only authors can update a draft"
            }
        elif not d:
            return {
                "error": "There is no draft with this id"
            }
        else:
            session.delete(d)
            session.commit()
            return {}


@mutation.field("updateDraft")  # TODO: draft input type
@login_required
async def update_draft(_, info, draft_input):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        d = session.query(
            DraftCollab
        ).where(
            DraftCollab.id == draft_input.id
        ).one()  # raises Error when not found
        if auth.user_id not in d.authors:
            # raise BaseHttpException("only owner can remove coauthors")
            return {
                "error": "Only authors can update draft"
            }
        elif not d:
            return {
                "error": "There is no draft with this id"
            }
        else:
            draft_input["updatedAt"] = datetime.now(tz=timezone.utc)
            d.update(draft_input)
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
        elif c.id:
            invited_user = session.query(User).where(User.id == author).one()
            da = DraftAuthor.create({
                "accepted": False,
                "collab": c.id,
                "author": invited_user.id
            })
            session.add(da)
            session.commit()
        else:
            return {
                "error": "Draft is not found"
            }

    # TODO: email notify
    return {}


def get_slug(src):
    slug = translit(src, "ru", reversed=True).replace(".", "-").lower()
    slug = re.sub('[^0-9a-zA-Z]+', '-', slug)
    return slug


@mutation.field("inviteAccept")
@login_required
async def accept_coauthor(_, info, draft: int):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        d = session.query(DraftCollab).where(DraftCollab.id == draft).one()
        if not d:
            return {
                "error": "Draft id was not found"
            }
        else:
            a = session.query(DraftAuthor).where(DraftAuthor.collab == draft).filter(
                DraftAuthor.author == auth.user_id).one()
            if not a.accepted:
                a.accepted = True
                session.commit()
                # TODO: email notify
                return {}
            elif a.accepted:
                return {
                    "error": "You have accepted invite before"
                }
            else:
                # raise BaseHttpException("only invited can accept")
                return {
                    "error": "You don't have an invitation yet"
                }


@mutation.field("draftToShout")
@login_required
async def draft_to_shout(_, info, draft: int = 0):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        d = session.query(DraftCollab).where(DraftCollab.id == draft).one()
        if auth.user_id not in d.authors:
            # raise BaseHttpException("you are not in authors list")
            return {
                "error": "You are not in authors list"
            }
        elif d.id:
            draft_authors = [a.author for a in d.authors]
            draft_topics = [t.topic for t in d.topics]
            authors = session.query(User).where(User.id._in(draft_authors)).all()
            topics = session.query(Topic).where(Topic.id._in(draft_topics)).all()
            new_shout = Shout.create({
                "authors": authors,
                "body": d.body,
                "title": d.title,
                "subtitle": d.subtitle or "",
                "topics": topics,
                "media": d.media,
                "slug": d.slug or get_slug(d.title),
                "layout": d.layout or "article"
            })
            session.add(new_shout)
            session.commit()
        else:
            return {
                "error": "Draft is not found"
            }

    # TODO: email notify
    return {}