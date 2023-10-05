from typing import List
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func, distinct, select, literal
from sqlalchemy.orm import aliased, joinedload

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from services.orm import local_session
from services.schema import mutation, query
from orm.reaction import Reaction
from orm.shout import ShoutAuthor, ShoutTopic
from orm.topic import Topic
from orm.user import AuthorFollower, Role, User, UserRating, UserRole

# from .community import followed_communities
from resolvers.inbox.unread import get_total_unread_counter
from resolvers.zine.topics import followed_by_user


def add_author_stat_columns(q, include_heavy_stat=False):
    author_followers = aliased(AuthorFollower)
    author_following = aliased(AuthorFollower)
    shout_author_aliased = aliased(ShoutAuthor)

    q = q.outerjoin(shout_author_aliased).add_columns(
        func.count(distinct(shout_author_aliased.shout)).label("shouts_stat")
    )
    q = q.outerjoin(author_followers, author_followers.author == User.id).add_columns(
        func.count(distinct(author_followers.follower)).label("followers_stat")
    )

    q = q.outerjoin(author_following, author_following.follower == User.id).add_columns(
        func.count(distinct(author_following.author)).label("followings_stat")
    )

    if include_heavy_stat:
        user_rating_aliased = aliased(UserRating)
        q = q.outerjoin(
            user_rating_aliased, user_rating_aliased.user == User.id
        ).add_columns(func.sum(user_rating_aliased.value).label("rating_stat"))

    else:
        q = q.add_columns(literal(-1).label("rating_stat"))

    if include_heavy_stat:
        q = q.outerjoin(
            Reaction, and_(Reaction.createdBy == User.id, Reaction.body.is_not(None))
        ).add_columns(func.count(distinct(Reaction.id)).label("commented_stat"))
    else:
        q = q.add_columns(literal(-1).label("commented_stat"))

    q = q.group_by(User.id)

    return q


def add_stat(author, stat_columns):
    [
        shouts_stat,
        followers_stat,
        followings_stat,
        rating_stat,
        commented_stat,
    ] = stat_columns
    author.stat = {
        "shouts": shouts_stat,
        "followers": followers_stat,
        "followings": followings_stat,
        "rating": rating_stat,
        "commented": commented_stat,
    }

    return author


def get_authors_from_query(q):
    authors = []
    with local_session() as session:
        for [author, *stat_columns] in session.execute(q):
            author = add_stat(author, stat_columns)
            authors.append(author)

    return authors


async def user_subscriptions(user_id: int):
    return {
        "unread": await get_total_unread_counter(
            user_id
        ),  # unread inbox messages counter
        "topics": [
            t.slug for t in await followed_topics(user_id)
        ],  # followed topics slugs
        "authors": [
            a.slug for a in await followed_authors(user_id)
        ],  # followed authors slugs
        "reactions": await followed_reactions(user_id)
        # "communities": [c.slug for c in followed_communities(slug)],  # communities
    }


# @query.field("userFollowedDiscussions")
# @login_required
async def followed_discussions(_, info, user_id) -> List[Topic]:
    return await followed_reactions(user_id)


async def followed_reactions(user_id):
    with local_session() as session:
        user = session.query(User).where(User.id == user_id).first()
        return (
            session.query(Reaction.shout)
            .where(Reaction.createdBy == user.id)
            .filter(Reaction.createdAt > user.lastSeen)
            .all()
        )


# dufok mod (^*^') :
@query.field("userFollowedTopics")
async def get_followed_topics(_, info, slug) -> List[Topic]:
    user_id_query = select(User.id).where(User.slug == slug)
    with local_session() as session:
        user_id = session.execute(user_id_query).scalar()

    if user_id is None:
        raise ValueError("User not found")

    return await followed_topics(user_id)


async def followed_topics(user_id):
    return followed_by_user(user_id)


# dufok mod (^*^') :
@query.field("userFollowedAuthors")
async def get_followed_authors(_, _info, slug) -> List[User]:
    # 1. First, we need to get the user_id for the given slug
    user_id_query = select(User.id).where(User.slug == slug)
    with local_session() as session:
        user_id = session.execute(user_id_query).scalar()

    if user_id is None:
        raise ValueError("User not found")

    return await followed_authors(user_id)


# 2. Now, we can use the user_id to get the followed authors
async def followed_authors(user_id):
    q = select(User)
    q = add_author_stat_columns(q)
    q = q.join(AuthorFollower, AuthorFollower.author == User.id).where(
        AuthorFollower.follower == user_id
    )
    # 3. Pass the query to the get_authors_from_query function and return the results
    return get_authors_from_query(q)


@query.field("userFollowers")
async def user_followers(_, _info, slug) -> List[User]:
    q = select(User)
    q = add_author_stat_columns(q)

    aliased_user = aliased(User)
    q = (
        q.join(AuthorFollower, AuthorFollower.follower == User.id)
        .join(aliased_user, aliased_user.id == AuthorFollower.author)
        .where(aliased_user.slug == slug)
    )

    return get_authors_from_query(q)


async def get_user_roles(slug):
    with local_session() as session:
        user = session.query(User).where(User.slug == slug).first()
        roles = (
            session.query(Role)
            .options(joinedload(Role.permissions))
            .join(UserRole)
            .where(UserRole.user == user.id)
            .all()
        )

    return roles


@mutation.field("updateProfile")
@login_required
async def update_profile(_, info, profile):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        user = session.query(User).filter(User.id == user_id).one()
        if not user:
            return {"error": "canoot find user"}
        user.update(profile)
        session.commit()
    return {"error": None, "author": user}


@mutation.field("rateUser")
@login_required
async def rate_user(_, info, rated_userslug, value):
    auth: AuthCredentials = info.context["request"].auth

    with local_session() as session:
        rating = (
            session.query(UserRating)
            .filter(
                and_(
                    UserRating.rater == auth.user_id, UserRating.user == rated_userslug
                )
            )
            .first()
        )
        if rating:
            rating.value = value
            session.commit()
            return {}
    try:
        UserRating.create(rater=auth.user_id, user=rated_userslug, value=value)
    except Exception as err:
        return {"error": err}
    return {}


# for mutation.field("follow")
def author_follow(user_id, slug):
    try:
        with local_session() as session:
            author = session.query(User).where(User.slug == slug).one()
            af = AuthorFollower.create(follower=user_id, author=author.id)
            session.add(af)
            session.commit()
        return True
    except:
        return False


# for mutation.field("unfollow")
def author_unfollow(user_id, slug):
    with local_session() as session:
        flw = (
            session.query(AuthorFollower)
            .join(User, User.id == AuthorFollower.author)
            .filter(and_(AuthorFollower.follower == user_id, User.slug == slug))
            .first()
        )
        if flw:
            session.delete(flw)
            session.commit()
            return True
    return False


@query.field("authorsAll")
async def get_authors_all(_, _info):
    q = select(User)
    q = add_author_stat_columns(q)
    q = q.join(ShoutAuthor, User.id == ShoutAuthor.user)

    return get_authors_from_query(q)


@query.field("getAuthor")
async def get_author(_, _info, slug):
    q = select(User).where(User.slug == slug)
    q = add_author_stat_columns(q, True)

    authors = get_authors_from_query(q)
    return authors[0]


@query.field("loadAuthorsBy")
async def load_authors_by(_, info, by, limit, offset):
    q = select(User)
    q = add_author_stat_columns(q)
    if by.get("slug"):
        q = q.filter(User.slug.ilike(f"%{by['slug']}%"))
    elif by.get("name"):
        q = q.filter(User.name.ilike(f"%{by['name']}%"))
    elif by.get("topic"):
        q = (
            q.join(ShoutAuthor)
            .join(ShoutTopic)
            .join(Topic)
            .where(Topic.slug == by["topic"])
        )
    if by.get("lastSeen"):  # in days
        days_before = datetime.now(tz=timezone.utc) - timedelta(days=by["lastSeen"])
        q = q.filter(User.lastSeen > days_before)
    elif by.get("createdAt"):  # in days
        days_before = datetime.now(tz=timezone.utc) - timedelta(days=by["createdAt"])
        q = q.filter(User.createdAt > days_before)

    q = q.order_by(by.get("order", User.createdAt)).limit(limit).offset(offset)

    return get_authors_from_query(q)
