from typing import List
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func, distinct, select
from sqlalchemy.orm import aliased, joinedload

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction
from orm.shout import ShoutAuthor, ShoutTopic
from orm.topic import Topic
from orm.user import AuthorFollower, Role, User, UserRating, UserRole

# from .community import followed_communities
from resolvers.inbox.unread import get_total_unread_counter
from resolvers.zine.topics import followed_by_user


def add_author_stat_columns(q):
    author_followers = aliased(AuthorFollower)
    author_following = aliased(AuthorFollower)

    q = q.outerjoin(ShoutAuthor).add_columns(
        func.count(distinct(ShoutAuthor.shout)).label('shouts_stat')
    ).outerjoin(author_followers, author_followers.author == User.slug).add_columns(
        func.count(distinct(author_followers.follower)).label('followers_stat')
    ).outerjoin(author_following, author_following.follower == User.slug).add_columns(
        func.count(distinct(author_following.author)).label('followings_stat')
    ).outerjoin(UserRating).add_columns(
        # TODO: check
        func.sum(UserRating.value).label('rating_stat')
    ).outerjoin(Reaction, and_(Reaction.createdBy == User.slug, Reaction.body.is_not(None))).add_columns(
        func.count(distinct(Reaction.id)).label('commented_stat')
    )

    q = q.group_by(User.id)

    return q


def add_stat(author, stat_columns):
    [shouts_stat, followers_stat, followings_stat, rating_stat, commented_stat] = stat_columns
    author.stat = {
        "shouts": shouts_stat,
        "followers": followers_stat,
        "followings": followings_stat,
        "rating": rating_stat,
        "commented": commented_stat
    }

    return author


def get_authors_from_query(q):
    authors = []
    with local_session() as session:
        for [author, *stat_columns] in session.execute(q):
            author = add_stat(author, stat_columns)
            authors.append(author)

    return authors


async def user_subscriptions(slug: str):
    return {
        "unread": await get_total_unread_counter(slug),  # unread inbox messages counter
        "topics": [t.slug for t in await followed_topics(slug)],  # followed topics slugs
        "authors": [a.slug for a in await followed_authors(slug)],  # followed authors slugs
        "reactions": await followed_reactions(slug)
        # "communities": [c.slug for c in followed_communities(slug)],  # communities
    }


# @query.field("userFollowedDiscussions")
@login_required
async def followed_discussions(_, info, slug) -> List[Topic]:
    return await followed_reactions(slug)


async def followed_reactions(slug):
    with local_session() as session:
        user = session.query(User).where(User.slug == slug).first()
        return session.query(
            Reaction.shout
        ).where(
            Reaction.createdBy == slug
        ).filter(
            Reaction.createdAt > user.lastSeen
        ).all()


@query.field("userFollowedTopics")
@login_required
async def get_followed_topics(_, info, slug) -> List[Topic]:
    return await followed_topics(slug)


async def followed_topics(slug):
    return followed_by_user(slug)


@query.field("userFollowedAuthors")
async def get_followed_authors(_, _info, slug) -> List[User]:
    return await followed_authors(slug)


async def followed_authors(slug) -> List[User]:
    q = select(User)
    q = add_author_stat_columns(q)
    q = q.join(AuthorFollower).where(AuthorFollower.follower == slug)

    return get_authors_from_query(q)


@query.field("userFollowers")
async def user_followers(_, _info, slug) -> List[User]:
    q = select(User)
    q = add_author_stat_columns(q)
    q = q.join(AuthorFollower).where(AuthorFollower.author == slug)

    return get_authors_from_query(q)


async def get_user_roles(slug):
    with local_session() as session:
        user = session.query(User).where(User.slug == slug).first()
        roles = (
            session.query(Role)
                .options(joinedload(Role.permissions))
                .join(UserRole)
                .where(UserRole.user_id == user.id)
                .all()
        )

    return roles


@mutation.field("updateProfile")
@login_required
async def update_profile(_, info, profile):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            User.update(user, **profile)
            session.add(user)
            session.commit()
    return {}


@mutation.field("rateUser")
@login_required
async def rate_user(_, info, rated_userslug, value):
    user = info.context["request"].user
    with local_session() as session:
        rating = (
            session.query(UserRating)
                .filter(and_(UserRating.rater == user.slug, UserRating.user == rated_userslug))
                .first()
        )
        if rating:
            rating.value = value
            session.commit()
            return {}
    try:
        UserRating.create(rater=user.slug, user=rated_userslug, value=value)
    except Exception as err:
        return {"error": err}
    return {}


# for mutation.field("follow")
def author_follow(user, slug):
    with local_session() as session:
        af = AuthorFollower.create(follower=user.slug, author=slug)
        session.add(af)
        session.commit()


# for mutation.field("unfollow")
def author_unfollow(user, slug):
    with local_session() as session:
        flw = (
            session.query(AuthorFollower)
                .filter(
                and_(
                    AuthorFollower.follower == user.slug, AuthorFollower.author == slug
                )
            )
                .first()
        )
        if not flw:
            raise Exception("[resolvers.profile] follower not exist, cant unfollow")
        else:
            session.delete(flw)
            session.commit()


@query.field("authorsAll")
async def get_authors_all(_, _info):
    q = select(User)
    q = add_author_stat_columns(q)
    q = q.join(ShoutAuthor)

    return get_authors_from_query(q)


@query.field("getAuthor")
async def get_author(_, _info, slug):
    q = select(User).where(User.slug == slug)
    q = add_author_stat_columns(q)

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
        q = q.join(ShoutAuthor).join(ShoutTopic).where(ShoutTopic.topic == by["topic"])
    if by.get("lastSeen"):  # in days
        days_before = datetime.now(tz=timezone.utc) - timedelta(days=by["lastSeen"])
        q = q.filter(User.lastSeen > days_before)
    elif by.get("createdAt"):  # in days
        days_before = datetime.now(tz=timezone.utc) - timedelta(days=by["createdAt"])
        q = q.filter(User.createdAt > days_before)

    q = q.order_by(
        by.get("order", User.createdAt)
    ).limit(limit).offset(offset)

    return get_authors_from_query(q)
