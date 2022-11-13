from datetime import datetime

from sqlalchemy import and_, desc

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutReactionsFollower
from orm.user import User
from services.auth.users import UserStorage
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage


async def get_reaction_stat(reaction_id):
    return {
        "viewed": await ViewedStorage.get_reaction(reaction_id),
        "reacted": len(await ReactedStorage.get_reaction(reaction_id)),
        "rating": await ReactedStorage.get_reaction_rating(reaction_id),
        "commented": len(await ReactedStorage.get_reaction_comments(reaction_id)),
    }


def reactions_follow(user: User, slug: str, auto=False):
    with local_session() as session:
        following = (
            session.query(ShoutReactionsFollower)
            .where(and_(
                ShoutReactionsFollower.follower == user.slug,
                ShoutReactionsFollower.shout == slug
            ))
            .first()
        )
        if not following:
            following = ShoutReactionsFollower.create(
                follower=user.slug,
                shout=slug,
                auto=auto
            )
            session.add(following)
            session.commit()


def reactions_unfollow(user, slug):
    with local_session() as session:
        following = (
            session.query(ShoutReactionsFollower)
            .where(and_(
                ShoutReactionsFollower.follower == user.slug,
                ShoutReactionsFollower.shout == slug
            ))
            .first()
        )
        if following:
            session.delete(following)
            session.commit()


def is_published_author(session, userslug):
    ''' checks if user has at least one publication '''
    return session.query(
        Shout
    ).where(
        Shout.authors.contains(userslug)
    ).filter(
        and_(
            Shout.publishedAt.is_not(None),
            Shout.deletedAt.is_(None)
        )
    ).count() > 0


def check_to_publish(session, user, reaction):
    ''' set shout to public if publicated approvers amount > 4 '''
    if not reaction.replyTo and reaction.kind in [
        ReactionKind.ACCEPT,
        ReactionKind.LIKE,
        ReactionKind.PROOF
    ]:
        if is_published_author(user):
            # now count how many approvers are voted already
            approvers_reactions = session.query(Reaction).where(Reaction.shout == reaction.shout).all()
            approvers = [user.slug, ]
            for ar in approvers_reactions:
                a = ar.createdBy
                if is_published_author(session, a):
                    approvers.append(a)
            if len(approvers) > 4:
                return True
    return False


def check_to_hide(session, user, reaction):
    ''' hides any shout if 20% of reactions are negative '''
    if not reaction.replyTo and reaction.kind in [
        ReactionKind.DECLINE,
        ReactionKind.UNLIKE,
        ReactionKind.UNPROOF
    ]:
        # if is_published_author(user):
        approvers_reactions = session.query(Reaction).where(Reaction.shout == reaction.shout).all()
        declines = 0
        for r in approvers_reactions:
            if r.kind in [
                ReactionKind.DECLINE,
                ReactionKind.UNLIKE,
                ReactionKind.UNPROOF
            ]:
                declines += 1
        if len(approvers_reactions) / declines < 5:
            return True
    return False


def set_published(session, slug, publisher):
    s = session.query(Shout).where(Shout.slug == slug).first()
    s.publishedAt = datetime.now()
    s.publishedBy = publisher
    s.visibility = 'public'
    session.add(s)
    session.commit()


def set_hidden(session, slug):
    s = session.query(Shout).where(Shout.slug == slug).first()
    s.visibility = 'authors'
    s.publishedAt = None  # TODO: discuss
    s.publishedBy = None  # TODO: store changes history in git
    session.add(s)
    session.commit()


@mutation.field("createReaction")
@login_required
async def create_reaction(_, info, inp):
    user = info.context["request"].user

    with local_session() as session:
        reaction = Reaction.create(**inp)
        session.add(reaction)
        session.commit()

        # self-regulation mechanics

        if check_to_hide(session, user, reaction):
            set_hidden(session, reaction.shout)
        elif check_to_publish(session, user, reaction):
            set_published(session, reaction.shout, reaction.createdBy)

    ReactedStorage.react(reaction)
    try:
        reactions_follow(user, inp["shout"], True)
    except Exception as e:
        print(f"[resolvers.reactions] error on reactions autofollowing: {e}")

    reaction.stat = await get_reaction_stat(reaction.id)
    return {"reaction": reaction}


@mutation.field("updateReaction")
@login_required
async def update_reaction(_, info, inp):
    auth = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        user = session.query(User).where(User.id == user_id).first()
        reaction = session.query(Reaction).filter(Reaction.id == inp.id).first()
        if not reaction:
            return {"error": "invalid reaction id"}
        if reaction.createdBy != user.slug:
            return {"error": "access denied"}
        reaction.body = inp["body"]
        reaction.updatedAt = datetime.now()
        if reaction.kind != inp["kind"]:
            # NOTE: change mind detection can be here
            pass
        if inp.get("range"):
            reaction.range = inp.get("range")
        session.commit()

        reaction.stat = await get_reaction_stat(reaction.id)

    return {"reaction": reaction}


@mutation.field("deleteReaction")
@login_required
async def delete_reaction(_, info, rid):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        user = session.query(User).where(User.id == user_id).first()
        reaction = session.query(Reaction).filter(Reaction.id == rid).first()
        if not reaction:
            return {"error": "invalid reaction id"}
        if reaction.createdBy != user.slug:
            return {"error": "access denied"}
        reaction.deletedAt = datetime.now()
        session.commit()
    return {}


@query.field("reactionsForShouts")
async def get_reactions_for_shouts(_, info, shouts, offset, limit):
    return await reactions_for_shouts(shouts, offset, limit)


async def reactions_for_shouts(shouts, offset, limit):
    reactions = []
    with local_session() as session:
        for slug in shouts:
            reactions += (
                session.query(Reaction)
                .filter(Reaction.shout == slug)
                .where(Reaction.deletedAt.is_not(None))
                .order_by(desc("createdAt"))
                .offset(offset)
                .limit(limit)
                .all()
            )
    for r in reactions:
        r.stat = await get_reaction_stat(r.id)
        r.createdBy = await UserStorage.get_user(r.createdBy or "discours")
    return reactions
    reactions = []
    with local_session() as session:
        for slug in shouts:
            reactions += (
                session.query(Reaction)
                .filter(Reaction.shout == slug)
                .where(Reaction.deletedAt.is_not(None))
                .order_by(desc("createdAt"))
                .offset(offset)
                .limit(limit)
                .all()
            )
    for r in reactions:
        r.stat = await get_reaction_stat(r.id)
        r.createdBy = await UserStorage.get_user(r.createdBy or "discours")
    return reactions


@query.field("reactionsByAuthor")
async def get_reactions_by_author(_, info, slug, limit=50, offset=0):
    reactions = []
    with local_session() as session:
        reactions = (
            session.query(Reaction)
            .where(Reaction.createdBy == slug)
            .limit(limit)
            .offset(offset)
        )
    for r in reactions:
        r.stat = await get_reaction_stat(r.id)
        r.createdBy = await UserStorage.get_user(r.createdBy or "discours")
    return reactions
