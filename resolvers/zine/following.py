import asyncio
from base.orm import local_session
from base.resolvers import mutation, subscription
from auth.authenticate import login_required
from auth.credentials import AuthCredentials
# from resolvers.community import community_follow, community_unfollow
from orm.user import AuthorFollower
from orm.topic import TopicFollower
from orm.shout import ShoutReactionsFollower
from resolvers.zine.profile import author_follow, author_unfollow
from resolvers.zine.reactions import reactions_follow, reactions_unfollow
from resolvers.zine.topics import topic_follow, topic_unfollow
from services.following import Following, FollowingManager, FollowingResult
from graphql.type import GraphQLResolveInfo


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    auth: AuthCredentials = info.context["request"].auth

    try:
        if what == "AUTHOR":
            author_follow(auth.user_id, slug)
            result = FollowingResult("NEW", 'author', slug)
            await FollowingManager.put('author', result)
        elif what == "TOPIC":
            topic_follow(auth.user_id, slug)
            result = FollowingResult("NEW", 'topic', slug)
            await FollowingManager.put('topic', result)
        elif what == "COMMUNITY":
            # community_follow(user, slug)
            # result = FollowingResult("NEW", 'community', slug)
            # await FollowingManager.put('community', result)
            pass
        elif what == "REACTIONS":
            reactions_follow(auth.user_id, slug)
            result = FollowingResult("NEW", 'shout', slug)
            await FollowingManager.put('shout', result)
    except Exception as e:
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    auth: AuthCredentials = info.context["request"].auth

    try:
        if what == "AUTHOR":
            author_unfollow(auth.user_id, slug)
            result = FollowingResult("DELETED", 'author', slug)
            await FollowingManager.put('author', result)
        elif what == "TOPIC":
            topic_unfollow(auth.user_id, slug)
            result = FollowingResult("DELETED", 'topic', slug)
            await FollowingManager.put('topic', result)
        elif what == "COMMUNITY":
            # community_unfollow(user, slug)
            # result = FollowingResult("DELETED", 'community', slug)
            # await FollowingManager.put('community', result)
            pass
        elif what == "REACTIONS":
            reactions_unfollow(auth.user_id, slug)
            result = FollowingResult("DELETED", 'shout', slug)
            await FollowingManager.put('shout', result)
    except Exception as e:
        return {"error": str(e)}

    return {}


# by author and by topic
@subscription.source("newShout")
@login_required
async def shout_generator(_, info: GraphQLResolveInfo):
    print(f"[resolvers.zine] shouts generator {info}")
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id
    try:
        tasks = []

        with local_session() as session:

            # notify new shout by followed authors
            following_topics = session.query(TopicFollower).where(TopicFollower.follower == user_id).all()

            for topic_id in following_topics:
                following_topic = Following('topic', topic_id)
                await FollowingManager.register('topic', following_topic)
                following_topic_task = following_topic.queue.get()
                tasks.append(following_topic_task)

            # by followed topics
            following_authors = session.query(AuthorFollower).where(
                AuthorFollower.follower == user_id).all()

            for author_id in following_authors:
                following_author = Following('author', author_id)
                await FollowingManager.register('author', following_author)
                following_author_task = following_author.queue.get()
                tasks.append(following_author_task)

            # TODO: use communities
            # by followed communities
            # following_communities = session.query(CommunityFollower).where(
            #    CommunityFollower.follower == user_id).all()

            # for community_id in following_communities:
            #     following_community = Following('community', author_id)
            #     await FollowingManager.register('community', following_community)
            #     following_community_task = following_community.queue.get()
            #     tasks.append(following_community_task)

        while True:
            shout = await asyncio.gather(*tasks)
            yield shout
    finally:
        pass


@subscription.source("newReaction")
@login_required
async def reaction_generator(_, info):
    print(f"[resolvers.zine] reactions generator {info}")
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id
    try:
        with local_session() as session:
            followings = session.query(ShoutReactionsFollower.shout).where(
                ShoutReactionsFollower.follower == user_id).unique()

            # notify new reaction

            tasks = []
            for shout_id in followings:
                following_shout = Following('shout', shout_id)
                await FollowingManager.register('shout', following_shout)
                following_author_task = following_shout.queue.get()
                tasks.append(following_author_task)

            while True:
                reaction = await asyncio.gather(*tasks)
                yield reaction
    finally:
        pass
