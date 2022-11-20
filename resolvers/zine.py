#!/usr/bin/env python3.10
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import desc, asc, select, case
from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.shout import Shout
from orm.reaction import Reaction, ReactionKind
# from resolvers.community import community_follow, community_unfollow
from resolvers.profile import author_follow, author_unfollow
from resolvers.reactions import reactions_follow, reactions_unfollow
from resolvers.topics import topic_follow, topic_unfollow
from services.zine.shoutauthor import ShoutAuthorStorage
from services.stat.reacted import ReactedStorage


@query.field("loadShout")
async def load_shout(_, info, slug):
    with local_session() as session:
        shout = session.query(Shout).options(
            # TODO add cation
            selectinload(Shout.authors),
            selectinload(Shout.topics),
        ).filter(
            Shout.slug == slug
        ).filter(
            Shout.deletedAt.is_(None)
        ).one()

        return shout


@query.field("loadShouts")
async def load_shouts_by(_, info, options):
    """
    :param options: {
        filters: {
            layout: 'audio',
            visibility: "public",
            author: 'discours',
            topic: 'culture',
            title: 'something',
            body: 'something else',
            days: 30
        }
        offset: 0
        limit: 50
        order_by: 'createdAt'
        order_by_desc: tr

    }
    :return: Shout[]
    """

    q = select(Shout).options(
        # TODO add caption
        selectinload(Shout.authors),
        selectinload(Shout.topics),
    ).where(
        Shout.deletedAt.is_(None)
    )

    if options.get("filters"):
        if options.get("filters").get("reacted"):
            user = info.context["request"].user
            q.join(Reaction, Reaction.createdBy == user.slug)
        if options.get("filters").get("visibility"):
            q = q.filter(Shout.visibility == options.get("filters").get("visibility"))
        if options.get("filters").get("layout"):
            q = q.filter(Shout.layout == options.get("filters").get("layout"))
        if options.get("filters").get("author"):
            q = q.filter(Shout.authors.any(slug=options.get("filters").get("author")))
        if options.get("filters").get("topic"):
            q = q.filter(Shout.topics.any(slug=options.get("filters").get("topic")))
        if options.get("filters").get("title"):
            q = q.filter(Shout.title.ilike(f'%{options.get("filters").get("title")}%'))
        if options.get("filters").get("body"):
            q = q.filter(Shout.body.ilike(f'%{options.get("filters").get("body")}%s'))
        if options.get("filters").get("days"):
            before = datetime.now() - timedelta(days=int(options.get("filter").get("days")) or 30)
            q = q.filter(Shout.createdAt > before)
    o = options.get("order_by")
    if o:
        q = q.add_columns(sa.func.count(Reaction.id).label(o))
        if o == 'comments':
            q = q.join(Reaction, Shout.slug == Reaction.shout)
            q = q.filter(Reaction.body.is_not(None))
        elif o == 'reacted':
            q = q.join(
                Reaction
            ).add_columns(
                sa.func.max(Reaction.createdAt).label(o)
            )
        elif o == "rating":
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
            )).label(options.get("order_by")))
        order_by = o
    else:
        order_by = 'createdAt'
    order_by_desc = True if options.get('order_by_desc') is None else options.get('order_by_desc')
    query_order_by = desc(order_by) if order_by_desc else asc(order_by)
    offset = options.get("offset") if options.get("offset") else 0
    limit = options.get("limit") or 10
    q = q.group_by(Shout.id).order_by(query_order_by).limit(limit).offset(offset)

    with local_session() as session:
        shouts = list(map(lambda r: r.Shout, session.execute(q)))
        for s in shouts:
            s.stat = await ReactedStorage.get_shout_stat(s.slug)
            for a in s.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)

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
