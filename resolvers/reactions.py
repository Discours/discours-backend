from sqlalchemy import desc
from sqlalchemy.orm import joinedload, selectinload
from orm.reaction import Reaction
from base.orm import local_session
from orm.shout import ShoutReactionsFollower
from orm.user import User
from base.resolvers import mutation, query
from auth.authenticate import login_required
from datetime import datetime
from services.auth.users import UserStorage
from services.stat.reacted import ReactedStorage

def reactions_follow(user, slug, auto=False):
    with local_session() as session:
        fw = session.query(ShoutReactionsFollower).\
            filter(ShoutReactionsFollower.follower == user.slug, ShoutReactionsFollower.shout == slug).\
            first()
        if auto and fw:
            return
        elif not auto and fw:
            if not fw.deletedAt is None:
                fw.deletedAt = None
                fw.auto = False
                session.commit()
                return
            # print("[resolvers.reactions] was followed before")

    ShoutReactionsFollower.create(
        follower=user.slug,
        shout=slug,
        auto=auto)


def reactions_unfollow(user, slug):
    with local_session() as session:
        following = session.query(ShoutReactionsFollower).\
            filter(ShoutReactionsFollower.follower == user.slug, ShoutReactionsFollower.shout == slug).\
            first()
        if not following:
            # print("[resolvers.reactions] was not followed", slug)
            return
        if following.auto:
            following.deletedAt = datetime.now()
        else:
            session.delete(following)
        session.commit()


@mutation.field("createReaction")
@login_required
async def create_reaction(_, info, inp):
    user = info.context["request"].user
    
    # TODO: filter allowed reaction kinds
    
    reaction = Reaction.create(**inp)
    ReactedStorage.increment(reaction.shout, reaction.replyTo)
    try:
        reactions_follow(user, inp['shout'], True)
    except Exception as e:
        print(f"[resolvers.reactions] error on reactions autofollowing: {e}")

    return {"reaction": reaction}


@mutation.field("updateReaction")
@login_required
async def update_reaction(_, info, inp):
    auth = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        reaction = session.query(Reaction).filter(Reaction.id == id).first()
        if not reaction:
            return {"error": "invalid reaction id"}
        if reaction.createdBy != user.slug:
            return {"error": "access denied"}
        reaction.body = inp['body']
        reaction.updatedAt = datetime.now()
        if reaction.kind != inp['kind']:
            # NOTE: change mind detection can be here
            pass
        if inp.get('range'):
            reaction.range = inp.get('range')
        session.commit()

    return {"reaction": reaction}


@mutation.field("deleteReaction")
@login_required
async def delete_reaction(_, info, id):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        reaction = session.query(Reaction).filter(Reaction.id == id).first()
        if not reaction:
            return {"error": "invalid reaction id"}
        if reaction.createdBy != user.slug:
            return {"error": "access denied"}
        reaction.deletedAt = datetime.now()
        session.commit()
    return {}

@query.field("reactionsByShout")
async def get_shout_reactions(_, info, slug, page, size):
    offset = page * size
    reactions = []
    with local_session() as session:
        reactions = session.query(Reaction).\
            filter(Reaction.shout == slug).\
            limit(size).offset(offset).all()
    for r in reactions:
        r.createdBy = await UserStorage.get_user(r.createdBy or 'discours')
    return reactions


@query.field("reactionsAll")
async def get_all_reactions(_, info, page=1, size=10):
    offset = page * size
    reactions = []
    with local_session() as session:
        reactions = session.query(Reaction).\
            filter(Reaction.deletedAt == None).\
            order_by(desc("createdAt")).\
            offset(offset).limit(size)
        for r in reactions:
            r.createdBy = await UserStorage.get_user(r.createdBy or 'discours')
        reactions = list(reactions)
        reactions.sort(key=lambda x: x.createdAt, reverse=True)
    return reactions

@query.field("reactionsByAuthor")
async def get_reactions_by_author(_, info, slug, page=1, size=50):
    offset = page * size
    reactions = []
    with local_session() as session:
        reactions = session.query(Reaction).filter(Reaction.createdBy == slug).limit(size).offset(offset)
    for r in reactions:
        r.createdBy = await UserStorage.get_user(r.createdBy or 'discours')
    return reactions