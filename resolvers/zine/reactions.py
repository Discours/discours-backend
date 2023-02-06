from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, asc, desc, select, text, func, case
from sqlalchemy.orm import aliased

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutReactionsFollower
from orm.user import User


def add_reaction_stat_columns(q):
    aliased_reaction = aliased(Reaction)

    q = q.outerjoin(aliased_reaction).add_columns(
        func.sum(
            aliased_reaction.id
        ).label('reacted_stat'),
        func.sum(
            case(
                (aliased_reaction.body.is_not(None), 1),
                else_=0
            )
        ).label('commented_stat'),
        func.sum(case(
            (aliased_reaction.kind == ReactionKind.AGREE, 1),
            (aliased_reaction.kind == ReactionKind.DISAGREE, -1),
            (aliased_reaction.kind == ReactionKind.PROOF, 1),
            (aliased_reaction.kind == ReactionKind.DISPROOF, -1),
            (aliased_reaction.kind == ReactionKind.ACCEPT, 1),
            (aliased_reaction.kind == ReactionKind.REJECT, -1),
            (aliased_reaction.kind == ReactionKind.LIKE, 1),
            (aliased_reaction.kind == ReactionKind.DISLIKE, -1),
            else_=0)
        ).label('rating_stat'))

    return q


def reactions_follow(user_id, shout_id: int, auto=False):
    with local_session() as session:
        shout = session.query(Shout).where(Shout.id == shout_id).one()

        following = (
            session.query(ShoutReactionsFollower).where(and_(
                ShoutReactionsFollower.follower == user_id,
                ShoutReactionsFollower.shout == shout.id,
            )).first()
        )

        if not following:
            following = ShoutReactionsFollower.create(
                follower=user_id,
                shout=shout.id,
                auto=auto
            )
            session.add(following)
            session.commit()


def reactions_unfollow(user_id: int, shout_id: int):
    with local_session() as session:
        shout = session.query(Shout).where(Shout.id == shout_id).one()

        following = (
            session.query(ShoutReactionsFollower).where(and_(
                ShoutReactionsFollower.follower == user_id,
                ShoutReactionsFollower.shout == shout.id
            )).first()
        )

        if following:
            session.delete(following)
            session.commit()


def is_published_author(session, user_id):
    ''' checks if user has at least one publication '''
    return session.query(
        Shout
    ).where(
        Shout.authors.contains(user_id)
    ).filter(
        and_(
            Shout.publishedAt.is_not(None),
            Shout.deletedAt.is_(None)
        )
    ).count() > 0


def check_to_publish(session, user_id, reaction):
    ''' set shout to public if publicated approvers amount > 4 '''
    if not reaction.replyTo and reaction.kind in [
        ReactionKind.ACCEPT,
        ReactionKind.LIKE,
        ReactionKind.PROOF
    ]:
        if is_published_author(user_id):
            # now count how many approvers are voted already
            approvers_reactions = session.query(Reaction).where(Reaction.shout == reaction.shout).all()
            approvers = [user_id, ]
            for ar in approvers_reactions:
                a = ar.createdBy
                if is_published_author(session, a):
                    approvers.append(a)
            if len(approvers) > 4:
                return True
    return False


def check_to_hide(session, user_id, reaction):
    ''' hides any shout if 20% of reactions are negative '''
    if not reaction.replyTo and reaction.kind in [
        ReactionKind.REJECT,
        ReactionKind.DISLIKE,
        ReactionKind.DISPROOF
    ]:
        # if is_published_author(user):
        approvers_reactions = session.query(Reaction).where(Reaction.shout == reaction.shout).all()
        rejects = 0
        for r in approvers_reactions:
            if r.kind in [
                ReactionKind.REJECT,
                ReactionKind.DISLIKE,
                ReactionKind.DISPROOF
            ]:
                rejects += 1
        if len(approvers_reactions) / rejects < 5:
            return True
    return False


def set_published(session, shout_id, publisher):
    s = session.query(Shout).where(Shout.id == shout_id).first()
    s.publishedAt = datetime.now(tz=timezone.utc)
    s.publishedBy = publisher
    s.visibility = text('public')
    session.add(s)
    session.commit()


def set_hidden(session, shout_id):
    s = session.query(Shout).where(Shout.id == shout_id).first()
    s.visibility = text('authors')
    s.publishedAt = None  # TODO: discuss
    s.publishedBy = None  # TODO: store changes history in git
    session.add(s)
    session.commit()


@mutation.field("createReaction")
@login_required
async def create_reaction(_, info, reaction={}):
    auth: AuthCredentials = info.context["request"].auth
    reaction['createdBy'] = auth.user_id
    with local_session() as session:
        r = Reaction.create(**reaction)
        shout = session.query(Shout).where(Shout.id == r.shout).one()

        # Proposal accepting logix
        if r.replyTo is not None and \
                r.kind == ReactionKind.ACCEPT and \
                auth.user_id in shout.dict()['authors']:
            replied_reaction = session.query(Reaction).when(Reaction.id == r.replyTo).first()
            if replied_reaction and replied_reaction.kind == ReactionKind.PROPOSE:
                if replied_reaction.range:
                    old_body = shout.body
                    start, end = replied_reaction.range.split(':')
                    start = int(start)
                    end = int(end)
                    new_body = old_body[:start] + replied_reaction.body + old_body[end:]
                    shout.body = new_body
                    # TODO: update git version control

        session.add(r)
        session.commit()

        print(r)

        # self-regulation mechanics

        if check_to_hide(session, auth.user_id, r):
            set_hidden(session, r.shout)
        elif check_to_publish(session, auth.user_id, r):
            set_published(session, r.shout, r.createdBy)

    try:
        reactions_follow(auth.user_id, reaction["shout"], True)
    except Exception as e:
        print(f"[resolvers.reactions] error on reactions autofollowing: {e}")

    r.stat = {
        "commented": 0,
        "reacted": 0,
        "rating": 0
    }
    return {"reaction": r}


@mutation.field("updateReaction")
@login_required
async def update_reaction(_, info, id, reaction={}):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        user = session.query(User).where(User.id == auth.user_id).first()
        q = select(Reaction).filter(Reaction.id == id)
        q = add_reaction_stat_columns(q)
        q = q.group_by(Reaction.id)

        [r, reacted_stat, commented_stat, rating_stat] = session.execute(q).unique().one()

        if not r:
            return {"error": "invalid reaction id"}
        if r.createdBy != user.id:
            return {"error": "access denied"}

        r.body = reaction["body"]
        r.updatedAt = datetime.now(tz=timezone.utc)
        if r.kind != reaction["kind"]:
            # NOTE: change mind detection can be here
            pass
        if reaction.get("range"):
            r.range = reaction.get("range")
        session.commit()
        r.stat = {
            "commented": commented_stat,
            "reacted": reacted_stat,
            "rating": rating_stat
        }

    return {"reaction": r}


@mutation.field("deleteReaction")
@login_required
async def delete_reaction(_, info, id):
    # NOTE: reaction is id
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        r = session.query(Reaction).filter(Reaction.id == id).first()
        if not r:
            return {"error": "invalid reaction id"}
        if r.createdBy != auth.user_id:
            return {"error": "access denied"}
        r.deletedAt = datetime.now(tz=timezone.utc)
        session.commit()
        return {
            "reaction": r
        }


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

    q = select(
        Reaction, User, Shout
    ).join(
        User, Reaction.createdBy == User.id
    ).join(
        Shout, Reaction.shout == Shout.id
    )

    if by.get("shout"):
        q = q.filter(Shout.slug == by["shout"])
    elif by.get("shouts"):
        q = q.filter(Shout.shout.in_(by["shouts"]))

    if by.get("createdBy"):
        q = q.filter(User.slug == by.get("createdBy"))

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
    order_field = by.get("sort", "").replace('-', '') or Reaction.createdAt

    q = q.group_by(
        Reaction.id, User.id, Shout.id
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
