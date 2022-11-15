from datetime import datetime, timedelta

from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import or_, desc, select

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.shout import Shout
from orm.reaction import Reaction
# from resolvers.community import community_follow, community_unfollow
from resolvers.profile import author_follow, author_unfollow
from resolvers.reactions import reactions_follow, reactions_unfollow
from resolvers.topics import topic_follow, topic_unfollow
from services.zine.shoutauthor import ShoutAuthorStorage
from services.stat.reacted import ReactedStorage


@query.field("loadShoutsBy")
async def load_shouts_by(_, info, by, amount=50, offset=0):
    """
    :param by: {
        layout: 'audio',
        visibility: "public",
        author: 'discours',
        topic: 'culture',
        title: 'something',
        body: 'something else',
        stat: 'rating' | 'comments' | 'reacted' | 'views',
        days: 30
    }
    :param amount: int amount of shouts
    :param offset: int offset in this order
    :return: Shout[]
    """

    q = select(Shout, Reaction).options(
        selectinload(Shout.authors),
        selectinload(Shout.topics),
        selectinload(Shout.reactions)
    ).where(
        Shout.deletedAt.is_(None)
    ).join(
        Reaction, Reaction.shout == Shout.slug
    )
    if by.get("slug"):
        q = q.filter(Shout.slug == by["slug"])
    else:
        if by.get("reacted"):
            user = info.context["request"].user
            q = q.filter(Reaction.createdBy == user.slug)
        if by.get("visibility"):
            q = q.filter(or_(
                Shout.visibility.ilike(f"%{by.get('visibility')}%"),
                Shout.visibility.ilike(f"%{'public'}%"),
            ))
        if by.get("layout"):
            q = q.filter(Shout.layout == by["layout"])
        if by.get("author"):
            q = q.filter(Shout.authors.contains(by["author"]))
        if by.get("topic"):
            q = q.filter(Shout.topics.contains(by["topic"]))
        if by.get("title"):
            q = q.filter(Shout.title.ilike(f'%{by["title"]}%'))
        if by.get("body"):
            q = q.filter(Shout.body.ilike(f'%{by["body"]}%'))
        if by.get("days"):
            before = datetime.now() - timedelta(days=int(by["days"]) or 30)
            q = q.filter(Shout.createdAt > before)
        q = q.group_by(Shout.id, Reaction.id).order_by(
            desc(by.get("order") or "createdAt")
        ).limit(amount).offset(offset)
    print(q)
    shouts = []
    with local_session() as session:
        # post query stats and author's captions
        for s in list(map(lambda r: r.Shout, session.execute(q))):
            s.stat = await ReactedStorage.get_shout_stat(s.slug)
            for a in s.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
            shouts.append(s)
        if by.get("stat"):
            shouts.sort(lambda s: s.stat.get(by["stat"]) or s.createdAt)
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
