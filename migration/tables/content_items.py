from datetime import datetime, timezone
import json
from dateutil.parser import parse as date_parse
from sqlalchemy.exc import IntegrityError
from transliterate import translit
from base.orm import local_session
from migration.extract import prepare_html_body
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutTopic, ShoutReactionsFollower
from orm.user import User
from orm.topic import TopicFollower
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage

OLD_DATE = "2016-03-05 22:22:00.350000"
ts = datetime.now(tz=timezone.utc)
type2layout = {
    "Article": "article",
    "Literature": "literature",
    "Music": "audio",
    "Video": "video",
    "Image": "image",
}


def get_shout_slug(entry):
    slug = entry.get("slug", "")
    if not slug:
        for friend in entry.get("friendlySlugs", []):
            slug = friend.get("slug", "")
            if slug:
                break
    return slug


def create_author_from_app(app):
    try:
        with local_session() as session:
            # check if email is used
            user = session.query(User).where(User.email == app['email']).first()
            if not user:
                name = app.get('name')
                slug = (
                    translit(name, "ru", reversed=True)
                    .replace(" ", "-")
                    .replace("'", "")
                    .replace(".", "-")
                    .lower()
                )
                # check if nameslug is used
                user = session.query(User).where(User.slug == slug).first()
                # get slug from email
                if user:
                    slug = app['email'].split('@')[0]
                    user = session.query(User).where(User.slug == slug).first()
                # one more try
                if user:
                    slug += '-author'
                    user = session.query(User).where(User.slug == slug).first()

                # create user with application data
                if not user:
                    userdata = {
                        "username": app["email"],
                        "email": app["email"],
                        "name": app.get("name", ""),
                        "bio": app.get("bio", ""),
                        "emailConfirmed": False,
                        "slug": slug,
                        "createdAt": ts,
                        "lastSeen": ts,
                    }
                    user = User.create(**userdata)
                    session.add(user)
                    session.commit()
            userdata = user.dict()
        if not userdata:
            userdata = User.default_user.dict()
    except Exception as e:
        print(app)
        raise e
    return userdata


async def create_shout(shout_dict, userslug):
    s = Shout.create(**shout_dict)
    with local_session() as session:
        srf = session.query(ShoutReactionsFollower).where(
            ShoutReactionsFollower.shout == s.slug
        ).filter(
            ShoutReactionsFollower.follower == userslug
        ).first()
        if not srf:
            srf = ShoutReactionsFollower.create(shout=s.slug, follower=userslug, auto=True)
            session.add(srf)
        session.commit()


async def migrate(entry, storage):
    # init, set title and layout
    r = {
        "layout": type2layout[entry["type"]],
        "title": entry["title"],
        "authors": [],
        "topics": set([])
    }
    topics_by_oid = storage["topics"]["by_oid"]
    users_by_oid = storage["users"]["by_oid"]
    # author
    oid = entry.get("createdBy", entry.get("_id", entry.get("oid")))
    userdata = users_by_oid.get(oid)
    user = None
    if not userdata:
        app = entry.get("application")
        if app:
            userdata = create_author_from_app(app)
    if userdata:
        userslug = userdata.get('slug')
    else:
        userslug = "anonymous"  # bad old id slug was found
    r["authors"] = [userslug, ]

    # slug
    slug = get_shout_slug(entry)
    if slug:
        r["slug"] = slug
    else:
        raise Exception

    # cover
    c = ""
    if entry.get("thumborId"):
        c = "https://assets.discours.io/unsafe/1600x/" + entry["thumborId"]
    else:
        c = entry.get("image", {}).get("url")
        if not c or "cloudinary" in c:
            c = ""
    r["cover"] = c

    # timestamps
    r["createdAt"] = date_parse(entry.get("createdAt", OLD_DATE))
    r["updatedAt"] = date_parse(entry["updatedAt"]) if "updatedAt" in entry else ts
    if entry.get("published"):
        r["publishedAt"] = date_parse(entry.get("publishedAt", OLD_DATE))
        r["visibility"] = "public"
        with local_session() as session:
            # update user.emailConfirmed if published
            author = session.query(User).where(User.slug == userslug).first()
            author.emailConfirmed = True
            session.add(author)
            session.commit()
    else:
        r["visibility"] = "authors"
    if "deletedAt" in entry:
        r["deletedAt"] = date_parse(entry["deletedAt"])

    # topics
    category = entry.get("category")
    for oid in [category, ] + entry.get("tags", []):
        t = storage["topics"]["by_oid"].get(oid)
        if t:
            tslug = storage["topics"]["by_oid"][oid]["slug"]
            r["topics"].add(tslug)
    r["topics"] = list(r["topics"])
    # main topic
    mt = topics_by_oid.get(category)
    if mt and mt.get("slug"):
        r["mainTopic"] = storage["replacements"].get(mt["slug"]) or r["topics"][0]

    # add author as TopicFollower
    with local_session() as session:
        for tpc in r['topics']:
            try:
                tf = session.query(
                    TopicFollower
                ).where(
                    TopicFollower.follower == userslug
                ).filter(
                    TopicFollower.topic == tpc
                ).first()
                if not tf:
                    tf = TopicFollower.create(
                        topic=tpc,
                        follower=userslug,
                        auto=True
                    )
                    session.add(tf)
            except IntegrityError:
                print('[migration.shout] hidden by topic ' + tpc)
                r["visibility"] = "authors"
                r["publishedAt"] = None
                r["topics"].remove(tpc)

    entry["topics"] = r["topics"]
    entry["cover"] = r["cover"]

    # body
    r["body"], media = prepare_html_body(entry)
    if media:
        r["media"] = json.dumps(media, ensure_ascii=True)
    # save shout to db
    s = object()
    shout_dict = r.copy()
    user = None
    del shout_dict["topics"]
    with local_session() as session:
        if not user and userslug:
            user = session.query(User).filter(User.slug == userslug).first()
        if not user and userdata:
            try:
                userdata["slug"] = userdata["slug"].lower().strip().replace(" ", "-")
                user = User.create(**userdata)
                session.add(user)
                session.commit()
            except IntegrityError:
                print("[migration] user error: " + userdata)
            userdata["id"] = user.id
            userdata["createdAt"] = user.createdAt
            storage["users"]["by_slug"][userdata["slug"]] = userdata
            storage["users"]["by_oid"][entry["_id"]] = userdata

    if not user:
        raise Exception("could not get a user")
    shout_dict["authors"] = [user, ]
    try:
        await create_shout(shout_dict, userslug)
    except IntegrityError as e:
        with local_session() as session:
            s = session.query(Shout).filter(Shout.slug == shout_dict["slug"]).first()
            bump = False
            if s:
                if s.authors[0] != userslug:
                    # create new with different slug
                    shout_dict["slug"] += '-' + shout_dict["layout"]
                    try:
                        await create_shout(shout_dict, userslug)
                    except IntegrityError as e:
                        print(e)
                        bump = True
                else:
                    # update old
                    for key in shout_dict:
                        if key in s.__dict__:
                            if s.__dict__[key] != shout_dict[key]:
                                print(
                                    "[migration] shout already exists, but differs in %s"
                                    % key
                                )
                                bump = True
                        else:
                            print("[migration] shout already exists, but lacks %s" % key)
                            bump = True
                    if bump:
                        s.update(shout_dict)
            else:
                print("[migration] something went wrong with shout: \n%r" % shout_dict)
                raise e
            session.commit()
    except Exception as e:
        print(e)
        print(s)
        raise Exception

    # shout topics aftermath
    shout_dict["topics"] = []
    for tpc in r["topics"]:
        oldslug = tpc
        newslug = storage["replacements"].get(oldslug, oldslug)
        if newslug:
            with local_session() as session:
                shout_topic_old = (
                    session.query(ShoutTopic)
                    .filter(ShoutTopic.shout == shout_dict["slug"])
                    .filter(ShoutTopic.topic == oldslug)
                    .first()
                )
                if shout_topic_old:
                    shout_topic_old.update({"slug": newslug})
                else:
                    shout_topic_new = (
                        session.query(ShoutTopic)
                        .filter(ShoutTopic.shout == shout_dict["slug"])
                        .filter(ShoutTopic.topic == newslug)
                        .first()
                    )
                    if not shout_topic_new:
                        try:
                            ShoutTopic.create(
                                **{"shout": shout_dict["slug"], "topic": newslug}
                            )
                        except Exception:
                            print("[migration] shout topic error: " + newslug)
                session.commit()
            if newslug not in shout_dict["topics"]:
                shout_dict["topics"].append(newslug)
        else:
            print("[migration] ignored topic slug: \n%r" % tpc["slug"])
            # raise Exception

    # content_item ratings to reactions
    try:
        with local_session() as session:
            for content_rating in entry.get("ratings", []):
                rater = (
                    session.query(User)
                    .filter(User.oid == content_rating["createdBy"])
                    .first()
                )
                reactedBy = (
                    rater
                    if rater
                    else session.query(User).filter(User.slug == "noname").first()
                )
                if rater:
                    reaction_dict = {
                        "kind": ReactionKind.LIKE
                        if content_rating["value"] > 0
                        else ReactionKind.DISLIKE,
                        "createdBy": reactedBy.slug,
                        "shout": shout_dict["slug"],
                    }
                    cts = content_rating.get("createdAt")
                    if cts:
                        reaction_dict["createdAt"] = date_parse(cts)
                    reaction = (
                        session.query(Reaction)
                        .filter(Reaction.shout == reaction_dict["shout"])
                        .filter(Reaction.createdBy == reaction_dict["createdBy"])
                        .filter(Reaction.kind == reaction_dict["kind"])
                        .first()
                    )
                    if reaction:
                        k = ReactionKind.AGREE if content_rating["value"] > 0 else ReactionKind.DISAGREE
                        reaction_dict["kind"] = k
                        reaction.update(reaction_dict)
                    else:
                        rea = Reaction.create(**reaction_dict)
                        session.add(rea)
                        await ReactedStorage.react(rea)
                    # shout_dict['ratings'].append(reaction_dict)

            session.commit()
    except Exception:
        raise Exception("[migration] content_item.ratings error: \n%r" % content_rating)

    # shout views
    await ViewedStorage.increment(shout_dict["slug"], amount=entry.get("views", 1))
    # del shout_dict['ratings']
    shout_dict["oid"] = entry.get("_id")
    storage["shouts"]["by_oid"][entry["_id"]] = shout_dict
    storage["shouts"]["by_slug"][slug] = shout_dict
    return shout_dict
