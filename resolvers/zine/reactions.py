from datetime import datetime, timedelta

from sqlalchemy import and_, asc, desc, select, text, func
from sqlalchemy.orm import selectinload
from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutReactionsFollower
from orm.user import User
from services.stat.reacted import ReactedStorage


async def get_reaction_stat(reaction_id):
    return {
        # "viewed": await ViewedStorage.get_reaction(reaction_id),
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
    s.visibility = text('public')
    session.add(s)
    session.commit()


def set_hidden(session, slug):
    s = session.query(Shout).where(Shout.slug == slug).first()
    s.visibility = text('authors')
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


def prepare_reactions(q, by):
    """ query filters and order """
    if by.get("shout"):
        q = q.filter(Shout.slug == by["shout"])
    elif by.get("shouts"):
        q = q.filter(Shout.slug.in_(by["shouts"]))
    if by.get("createdBy"):
        q = q.filter(Reaction.createdBy == by.get("createdBy"))
    if by.get("topic"):
        q = q.filter(Shout.topics.contains(by["topic"]))
    if by.get("body"):
        if by["body"] is True:
            q = q.filter(func.length(Reaction.body) > 0)
        else:
            q = q.filter(Reaction.body.ilike(f'%{by["body"]}%'))
    if by.get("days"):
        before = datetime.now() - timedelta(days=int(by["days"]) or 30)
        q = q.filter(Reaction.createdAt > before)
    order_way = asc if by.get("sort", "").startswith("-") else desc
    order_field = by.get("sort") or Reaction.createdAt
    q = q.group_by(
        Reaction.id
    ).order_by(
        order_way(order_field)
    )
    return q


@query.field("loadReactionsBy")
async def load_reactions_by(_, info, by, limit=50, offset=0):
    """
    :param by: {
        :shout - filter by slug
        :shouts - filer by shouts  luglist
        :createdBy - to filter by author
        :topic - to filter by topic
        :body - to search by body
        :days - a number of days ago
        :sort - a fieldname to sort desc by default
    }
    :param limit: int amount of shouts
    :param offset: int offset in this order
    :return: Reaction[]
    """
    user = None
    try:
        user = info.context["request"].user
    except Exception:
        pass

    q = select(
        Reaction
    ).options(
        selectinload(Reaction.createdBy),
        selectinload(Reaction.shout)
    ).join(
        User, Reaction.createdBy == User.slug
    ).join(
        Shout, Reaction.shout == Shout.slug
    ).where(
        Reaction.deletedAt.is_(None)
    )
    q = prepare_reactions(q, by)
    q = q.limit(limit).offset(offset)

    rrr = []
    with local_session() as session:
        # post query stats and author's captions
        for r in list(map(lambda r: r.Reaction, session.execute(q))):
            r.stat = await get_reaction_stat(r.id)
            rrr.append(r)
        if by.get("stat"):
            rrr.sort(lambda r: r.stat.get(by["stat"]) or r.createdAt)
    return rrr
