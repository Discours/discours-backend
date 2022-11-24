from typing import List
from datetime import datetime, timedelta
from sqlalchemy import and_, func
from sqlalchemy.orm import selectinload

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.reaction import Reaction
from orm.shout import ShoutAuthor
from orm.topic import Topic, TopicFollower
from orm.user import AuthorFollower, Role, User, UserRating, UserRole
from services.stat.reacted import ReactedStorage
from services.stat.topicstat import TopicStat

# from .community import followed_communities
from resolvers.inbox.unread import get_total_unread_counter
from .topics import get_topic_stat


async def user_subscriptions(slug: str):
    return {
        "unread": await get_total_unread_counter(slug),       # unread inbox messages counter
        "topics": [t.slug for t in await followed_topics(slug)],  # followed topics slugs
        "authors": [a.slug for a in await followed_authors(slug)],  # followed authors slugs
        "reactions": await ReactedStorage.get_shouts_by_author(slug),
        # "communities": [c.slug for c in followed_communities(slug)],  # communities
    }


async def get_author_stat(slug):
    # TODO: implement author stat
    with local_session() as session:
        return {
            "shouts": session.query(ShoutAuthor).where(ShoutAuthor.user == slug).count(),
            "followers": session.query(AuthorFollower).where(AuthorFollower.author == slug).count(),
            "followings": session.query(AuthorFollower).where(AuthorFollower.follower == slug).count(),
            "rating": session.query(func.sum(UserRating.value)).where(UserRating.user == slug).first(),
            "commented": session.query(
                Reaction.id
            ).where(
                Reaction.createdBy == slug
            ).filter(
                func.length(Reaction.body) > 0
            ).count()
        }


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


async def get_user_roles(slug):
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
    with local_session() as session:
        authors = session.query(User).join(ShoutAuthor).all()
        for author in authors:
            author.stat = await get_author_stat(author.slug)
    return authors


@query.field("getAuthor")
async def get_author(_, _info, slug):
    with local_session() as session:
        author = session.query(User).join(ShoutAuthor).where(User.slug == slug).first()
        for author in author:
            author.stat = await get_author_stat(author.slug)
    return author


@query.field("loadAuthorsBy")
async def load_authors_by(_, info, by, limit, offset):
    authors = []
    with local_session() as session:
        aq = session.query(User)
        if by.get("slug"):
            aq = aq.filter(User.slug.ilike(f"%{by['slug']}%"))
        elif by.get("name"):
            aq = aq.filter(User.name.ilike(f"%{by['name']}%"))
        elif by.get("topic"):
            aaa = list(map(lambda a: a.slug, TopicStat.authors_by_topic.get(by["topic"])))
            aq = aq.filter(User.name._in(aaa))
        if by.get("lastSeen"):  # in days
            days_before = datetime.now() - timedelta(days=by["lastSeen"])
            aq = aq.filter(User.lastSeen > days_before)
        elif by.get("createdAt"):  # in days
            days_before = datetime.now() - timedelta(days=by["createdAt"])
            aq = aq.filter(User.createdAt > days_before)
        aq = aq.group_by(
            User.id
        ).order_by(
            by.get("order") or "createdAt"
        ).limit(limit).offset(offset)
        print(aq)
        authors = list(map(lambda r: r.User, session.execute(aq)))
        if by.get("stat"):
            for a in authors:
                a.stat = await get_author_stat(a.slug)
    authors = list(set(authors))
    # authors = sorted(authors, key=lambda a: a["stat"].get(by.get("stat")))
    return authors
