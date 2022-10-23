from datetime import datetime

from sqlalchemy import desc, and_

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction
from orm.shout import ShoutReactionsFollower
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


@mutation.field("createReaction")
@login_required
async def create_reaction(_, info, inp):
    user = info.context["request"].user

    # TODO: filter allowed for post reaction kinds

    with local_session() as session:
        reaction = Reaction.create(**inp)
        session.add(reaction)
        session.commit()
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
