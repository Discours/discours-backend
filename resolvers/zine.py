from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import or_, desc, asc, select, case
from timeit import default_timer as timer
from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.shout import Shout
from orm.reaction import Reaction, ReactionsWeights, ReactionKind
# from resolvers.community import community_follow, community_unfollow
from resolvers.profile import author_follow, author_unfollow
from resolvers.reactions import reactions_follow, reactions_unfollow
from resolvers.topics import topic_follow, topic_unfollow
from services.zine.shoutauthor import ShoutAuthorStorage
from services.stat.reacted import ReactedStorage


@query.field("loadShoutsBy")
async def load_shouts_by(_, info, filter_by, limit, offset, order_by="createdAt", order_by_desc=True):
    """
    :param filterBy: {
        layout: 'audio',
        visibility: "public",
        author: 'discours',
        topic: 'culture',
        title: 'something',
        body: 'something else',
        days: 30
    }
    :param order_by: 'rating' | 'comments' | 'reacted' | 'views' | 'createdAt
    :param order_by_desc: order be desc/ask (desc by default)
    :param limit: int amount of shouts
    :param offset: int offset in this order
    :return: Shout[]
    """

    q = select(Shout).options(
        # TODO add cation
        selectinload(Shout.authors),
        selectinload(Shout.topics),
    ).where(
        Shout.deletedAt.is_(None)
    )

    if filter_by.get("slug"):
        q = q.filter(Shout.slug == filter_by["slug"])
    else:
        if filter_by.get("reacted"):
            user = info.context["request"].user
            q.join(Reaction, Reaction.createdBy == user.slug)
        if filter_by.get("visibility"):
            q = q.filter(or_(
                Shout.visibility.ilike(f"%{filter_by.get('visibility')}%"),
                Shout.visibility.ilike(f"%{'public'}%"),
            ))
        if filter_by.get("layout"):
            q = q.filter(Shout.layout == filter_by["layout"])
        if filter_by.get("author"):
            q = q.filter(Shout.authors.any(slug=filter_by["author"]))
        if filter_by.get("topic"):
            q = q.filter(Shout.topics.any(slug=filter_by["topic"]))
        if filter_by.get("title"):
            q = q.filter(Shout.title.ilike(f'%{filter_by["title"]}%'))
        if filter_by.get("body"):
            q = q.filter(Shout.body.ilike(f'%{filter_by["body"]}%'))
        if filter_by.get("days"):
            before = datetime.now() - timedelta(days=int(filter_by["days"]) or 30)
            q = q.filter(Shout.createdAt > before)
        if order_by == 'comments':
            q = q.join(Reaction).add_columns(sa.func.count(Reaction.id).label(order_by))
        if order_by == 'reacted':
            # TODO ?
            q = q.join(Reaction).add_columns(sa.func.count(Reaction.id).label(order_by))
        if order_by == "rating":
            q = q.join(Reaction).add_columns(sa.func.sum(case(
                (Reaction.kind == ReactionKind.AGREE, 1),
                (Reaction.kind == ReactionKind.DISAGREE, -1),
                (Reaction.kind == ReactionKind.PROOF, 1),
                (Reaction.kind == ReactionKind.DISPROOF, -1),
                (Reaction.kind == ReactionKind.ACCEPT, 1),
                (Reaction.kind == ReactionKind.REJECT, -1),
                (Reaction.kind == ReactionKind.LIKE, 1),
                (Reaction.kind == ReactionKind.DISLIKE, -1),
                else_=0
            )).label(order_by))
        # if order_by == 'views':
        # TODO dump ackee data to db periodically

        query_order_by = desc(order_by) if order_by_desc else asc(order_by)

        q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

        with local_session() as session:
            # post query stats and author's captions
            # start = timer()
            shouts = list(map(lambda r: r.Shout, session.execute(q)))
            for s in shouts:
                s.stat = await ReactedStorage.get_shout_stat(s.slug)
                for a in s.authors:
                    a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)

            # end = timer()
            # print(end - start)
            # print(q)

        return shouts


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    user = info.context["request"].user
    try:
        if what == "AUTHOR":
            author_follow(user, slug)
        elif what == "TOPIC":
            topic_follow(user, slug)
        elif what == "COMMUNITY":
            # community_follow(user, slug)
            pass
        elif what == "REACTIONS":
            reactions_follow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    user = info.context["request"].user

    try:
        if what == "AUTHOR":
            author_unfollow(user, slug)
        elif what == "TOPIC":
            topic_unfollow(user, slug)
        elif what == "COMMUNITY":
            # community_unfollow(user, slug)
            pass
        elif what == "REACTIONS":
            reactions_unfollow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}
