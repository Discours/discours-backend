from sqlalchemy import and_
from sqlalchemy.orm import selectinload, joinedload
from orm.reaction import Reaction
from orm.base import local_session
from orm.shout import Shout, ShoutReactionsFollower
from orm.user import User
from resolvers.base import mutation, query
from auth.authenticate import login_required
from datetime import datetime
from storages.reactions import ReactionsStorage
from storages.viewed import ViewedStorage


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

    reaction = Reaction.create(**inp)

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
            # TODO: change mind detection
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
def get_shout_reactions(_, info, slug) -> list[Shout]: 
    shouts = []
    with local_session() as session:
        shoutslugs = session.query(ShoutReactionsFollower.shout).\
            join(User).where(Reaction.createdBy == User.slug).\
            filter(ShoutReactionsFollower.follower == slug,
                   ShoutReactionsFollower.deletedAt == None).all()
        shoutslugs = list(set(shoutslugs))
        shouts = session.query(Shout).filter(Shout.slug in shoutslugs).all()
    return shouts


@query.field("reactionsAll")
def get_all_reactions(_, info, page=1, size=10) -> list[Reaction]:
    reactions = []
    with local_session() as session:
        q = session.query(Reaction).\
            options(
                joinedload(User), 
                joinedload(Shout)
            ).\
            join( User, Reaction.createdBy == User.slug ).\
            join( Shout, Reaction.shout == Shout.slug ).\
            filter( Reaction.deletedAt == None ).\
            limit(size).offset(page * size).all()
        # print(reactions[0].dict())
        return reactions


@query.field("reactionsByAuthor")
def get_reactions_by_author(_, info, slug, page=1, size=50) -> list[Reaction]:
    reactions = []
    with local_session() as session:
        reactions = session.query(Reaction).\
            join(Shout).where(Reaction.shout == Shout.slug).\
            filter(Reaction.deletedAt == None, Reaction.createdBy == slug).\
        	limit(size).offset(page * size).all() # pagination
        return reactions


@mutation.field("viewReaction")
async def view_reaction(_, info, reaction):
	await ViewedStorage.inc_reaction(reaction)
	return {"error" : ""}