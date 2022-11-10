from typing import List

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import selectinload

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction
from orm.shout import Shout
from orm.topic import Topic, TopicFollower
from orm.user import User, UserRole, Role, UserRating, AuthorFollower
from .community import followed_communities
from .inbox import get_total_unread_counter
from .topics import get_topic_stat
from services.auth.users import UserStorage
from services.zine.shoutscache import ShoutsCache
from services.stat.reacted import ReactedStorage


async def user_subscriptions(slug: str):
    return {
        "unread": await get_total_unread_counter(slug),       # unread inbox messages counter
        "topics": [t.slug for t in await followed_topics(slug)],  # followed topics slugs
        "authors": [a.slug for a in await followed_authors(slug)],  # followed authors slugs
        "reactions": await ReactedStorage.get_shouts_by_author(slug),
        "communities": [c.slug for c in followed_communities(slug)],  # communities
    }


async def get_author_stat(slug):
    # TODO: implement author stat
    with local_session() as session:
        return {
            "followers": session.query(AuthorFollower).where(AuthorFollower.author == slug).count(),
            "rating": session.query(func.sum(UserRating.value)).where(UserRating.user == slug).first()
        }


@query.field("userReactedShouts")
async def get_user_reacted_shouts(_, slug, offset, limit) -> List[Shout]:
    user = await UserStorage.get_user_by_slug(slug)
    if not user:
        return []
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(Reaction)
            .where(Reaction.createdBy == user.slug)
            .order_by(desc(Reaction.createdAt))
            .limit(limit)
            .offset()
            .all()
        )
    return shouts


@query.field("userFollowedTopics")
@login_required
async def get_followed_topics(_, info, slug) -> List[Topic]:
    return await followed_topics(slug)


async def followed_topics(slug):
    topics = []
    with local_session() as session:
        topics = (
            session.query(Topic)
            .join(TopicFollower)
            .where(TopicFollower.follower == slug)
            .all()
        )
        for topic in topics:
            topic.stat = await get_topic_stat(topic.slug)
    return topics


@query.field("userFollowedAuthors")
async def get_followed_authors(_, _info, slug) -> List[User]:
    return await followed_authors(slug)


async def followed_authors(slug) -> List[User]:
    authors = []
    with local_session() as session:
        authors = (
            session.query(User)
            .join(AuthorFollower, User.slug == AuthorFollower.author)
            .where(AuthorFollower.follower == slug)
            .all()
        )
        for author in authors:
            author.stat = await get_author_stat(author.slug)
    return authors


@query.field("userFollowers")
async def user_followers(_, _info, slug) -> List[User]:
    with local_session() as session:
        users = (
            session.query(User)
            .join(AuthorFollower, User.slug == AuthorFollower.follower)
            .where(AuthorFollower.author == slug)
            .all()
        )
    return users


@query.field("getUsersBySlugs")
async def get_users_by_slugs(_, _info, slugs):
    with local_session() as session:
        users = (
            session.query(User)
            .options(selectinload(User.ratings))
            .filter(User.slug in slugs)
            .all()
        )
    return users


@query.field("getUserRoles")
async def get_user_roles(_, _info, slug):
    with local_session() as session:
        user = session.query(User).where(User.slug == slug).first()
        roles = (
            session.query(Role)
            .options(selectinload(Role.permissions))
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
    users = await UserStorage.get_all_users()
    authorslugs = await ShoutsCache.get_all_authors_slugs()
    authors = []
    for author in users:
        if author.slug in authorslugs:
            author.stat = await get_author_stat(author.slug)
            authors.append(author)
    return authors


@query.field("topAuthors")
def get_top_authors(_, _info, offset, limit):
    return list(UserStorage.get_top_users())[offset : offset + limit]  # type: ignore


@query.field("getAuthor")
async def get_author(_, _info, slug):
    a = await UserStorage.users[slug]
    a.stat = get_author_stat(slug)
    return a
