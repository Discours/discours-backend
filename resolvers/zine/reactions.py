from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, asc, desc, select, text, func
from sqlalchemy.orm import aliased
from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutReactionsFollower
from orm.user import User
from resolvers.zine._common import add_common_stat_columns


def add_reaction_stat_columns(q):
    return add_common_stat_columns(q)


def reactions_follow(user: User, slug: str, auto=False):
    with local_session() as session:
        shout = session.query(Shout).where(Shout.slug == slug).one()

        following = (
            session.query(ShoutReactionsFollower).where(and_(
                ShoutReactionsFollower.follower_id == user.id,
                ShoutReactionsFollower.shout_id == shout.id,
            )).first()
        )

        if not following:
            following = ShoutReactionsFollower.create(
                follower_id=user.id,
                shout_id=shout.id,
                auto=auto
            )
            session.add(following)
            session.commit()


def reactions_unfollow(user, slug):
    with local_session() as session:
        shout = session.query(Shout).where(Shout.slug == slug).one()

        following = (
            session.query(ShoutReactionsFollower).where(and_(
                ShoutReactionsFollower.follower_id == user.id,
                ShoutReactionsFollower.shout_id == shout.id
            )).first()
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
            approvers_reactions = session.query(Reaction).where(Reaction.shout_id == reaction.shout_id).all()
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
        approvers_reactions = session.query(Reaction).where(Reaction.shout_id == reaction.shout_id).all()
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
    s.publishedAt = datetime.now(tz=timezone.utc)
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

    try:
        reactions_follow(user, inp["shout"], True)
    except Exception as e:
        print(f"[resolvers.reactions] error on reactions autofollowing: {e}")

    reaction.stat = {
        "commented": 0,
        "reacted": 0,
        "rating": 0
    }
    return {"reaction": reaction}


@mutation.field("updateReaction")
@login_required
async def update_reaction(_, info, inp):
    auth = info.context["request"].auth
    user_id = auth.user_id

    with local_session() as session:
        user = session.query(User).where(User.id == user_id).first()
        q = select(Reaction).filter(Reaction.id == inp.id)
        q = add_reaction_stat_columns(q)

        [reaction, reacted_stat, commented_stat, rating_stat] = session.execute(q).unique().one()

        if not reaction:
            return {"error": "invalid reaction id"}
        if reaction.createdBy != user.slug:
            return {"error": "access denied"}

        reaction.body = inp["body"]
        reaction.updatedAt = datetime.now(tz=timezone.utc)
        if reaction.kind != inp["kind"]:
            # NOTE: change mind detection can be here
            pass
        if inp.get("range"):
            reaction.range = inp.get("range")
        session.commit()
        reaction.stat = {
            "commented": commented_stat,
            "reacted": reacted_stat,
            "rating": rating_stat
        }

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
        reaction.deletedAt = datetime.now(tz=timezone.utc)
        session.commit()
    return {}


@query.field("loadReactionsBy")
async def load_reactions_by(_, _info, by, limit=50, offset=0):
    """
    :param by: {
        :shout - filter by slug
        :shouts - filer by shouts  luglist
        :createdBy - to filter by author
        :topic - to filter by topic
        :search - to search by reactions' body
        :comment - true if body.length > 0
        :days - a number of days ago
        :sort - a fieldname to sort desc by default
    }
    :param limit: int amount of shouts
    :param offset: int offset in this order
    :return: Reaction[]
    """

    CreatedByUser = aliased(User)
    ReactedShout = aliased(Shout)
    q = select(
        Reaction, CreatedByUser, ReactedShout
    ).join(
        CreatedByUser, Reaction.createdBy == CreatedByUser.id
    ).join(
        ReactedShout, Reaction.shout_id == ReactedShout.id
    )

    if by.get("shout"):
        aliased_shout = aliased(Shout)
        q = q.join(aliased_shout).filter(aliased_shout.slug == by["shout"])
    elif by.get("shouts"):
        aliased_shout = aliased(Shout)
        q = q.join(aliased_shout).filter(aliased_shout.shout.in_(by["shouts"]))
    if by.get("createdBy"):
        aliased_user = aliased(User)
        q = q.join(aliased_user).filter(aliased_user.slug == by.get("createdBy"))
    if by.get("topic"):
        # TODO: check
        q = q.filter(Shout.topics.contains(by["topic"]))
    if by.get("comment"):
        q = q.filter(func.length(Reaction.body) > 0)
    if len(by.get('search', '')) > 2:
        q = q.filter(Reaction.body.ilike(f'%{by["body"]}%'))
    if by.get("days"):
        after = datetime.now(tz=timezone.utc) - timedelta(days=int(by["days"]) or 30)
        q = q.filter(Reaction.createdAt > after)

    order_way = asc if by.get("sort", "").startswith("-") else desc
    # replace "-" -> "" ?
    order_field = by.get("sort") or Reaction.createdAt

    q = q.group_by(
        Reaction.id, CreatedByUser.id, ReactedShout.id
    ).order_by(
        order_way(order_field)
    )

    q = add_reaction_stat_columns(q)

    q = q.where(Reaction.deletedAt.is_(None))
    q = q.limit(limit).offset(offset)
    reactions = []

    with local_session() as session:
        for [reaction, user, shout, reacted_stat, commented_stat, rating_stat] in session.execute(q):
            reaction.createdBy = user
            reaction.shout = shout
            reaction.stat = {
                "rating": rating_stat,
                "commented": commented_stat,
                "reacted": reacted_stat
            }
            reactions.append(reaction)

    # ?
    if by.get("stat"):
        reactions.sort(lambda r: r.stat.get(by["stat"]) or r.createdAt)

    return reactions
