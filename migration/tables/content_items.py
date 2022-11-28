from datetime import datetime, timezone
import json
from dateutil.parser import parse as date_parse
from sqlalchemy.exc import IntegrityError
from transliterate import translit
from base.orm import local_session
from migration.extract import extract_html, extract_media
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutTopic, ShoutReactionsFollower
from orm.user import User
from orm.topic import TopicFollower
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

    # author
    users_by_oid = storage["users"]["by_oid"]
    user_oid = entry.get("createdBy", "")
    userdata = users_by_oid.get(user_oid)
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

    # visibility
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
    r['topics'] = await add_topics_follower(entry, storage, userslug)
    r['mainTopic'] = r['topics'][0]

    entry["topics"] = r["topics"]
    entry["cover"] = r["cover"]

    # body
    r["body"] = extract_html(entry)
    media = extract_media(entry)
    if media:
        r["media"] = json.dumps(media, ensure_ascii=True)

    shout_dict = r.copy()

    # user
    user = await get_user(userslug, userdata, storage, user_oid)
    shout_dict["authors"] = [user, ]
    del shout_dict["topics"]
    try:
        # save shout to db
        await create_shout(shout_dict, userslug)
    except IntegrityError as e:
        print(e)
        await resolve_create_shout(shout_dict, userslug)
    except Exception as e:
        raise Exception(e)

    # shout topics aftermath
    shout_dict["topics"] = await topics_aftermath(r, storage)

    # content_item ratings to reactions
    await content_ratings_to_reactions(entry, shout_dict["slug"])

    # shout views
    await ViewedStorage.increment(shout_dict["slug"], amount=entry.get("views", 1))
    # del shout_dict['ratings']

    shout_dict["oid"] = entry.get("_id", "")
    storage["shouts"]["by_oid"][entry["_id"]] = shout_dict
    storage["shouts"]["by_slug"][slug] = shout_dict
    return shout_dict


async def add_topics_follower(entry, storage, userslug):
    topics = set([])
    category = entry.get("category")
    topics_by_oid = storage["topics"]["by_oid"]
    oids = [category, ] + entry.get("tags", [])
    for toid in oids:
        tslug = topics_by_oid.get(toid, {}).get("slug")
        if tslug:
            topics.add(tslug)
    ttt = list(topics)
    # add author as TopicFollower
    with local_session() as session:
        for tpc in topics:
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
                    session.commit()
            except IntegrityError:
                print('[migration.shout] hidden by topic ' + tpc)
    # main topic
    maintopic = storage["replacements"].get(topics_by_oid.get(category, {}).get("slug"))
    if maintopic in ttt:
        ttt.remove(maintopic)
    ttt.insert(0, maintopic)
    return ttt


async def get_user(userslug, userdata, storage, oid):
    user = None
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
            storage["users"]["by_oid"][oid] = userdata
    if not user:
        raise Exception("could not get a user")
    return user


async def resolve_create_shout(shout_dict, userslug):
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
            raise Exception("")
        session.commit()


async def topics_aftermath(entry, storage):
    r = []
    for tpc in filter(lambda x: bool(x), entry["topics"]):
        oldslug = tpc
        newslug = storage["replacements"].get(oldslug, oldslug)
        if newslug:
            with local_session() as session:
                shout_topic_old = (
                    session.query(ShoutTopic)
                    .filter(ShoutTopic.shout == entry["slug"])
                    .filter(ShoutTopic.topic == oldslug)
                    .first()
                )
                if shout_topic_old:
                    shout_topic_old.update({"slug": newslug})
                else:
                    shout_topic_new = (
                        session.query(ShoutTopic)
                        .filter(ShoutTopic.shout == entry["slug"])
                        .filter(ShoutTopic.topic == newslug)
                        .first()
                    )
                    if not shout_topic_new:
                        try:
                            ShoutTopic.create(
                                **{"shout": entry["slug"], "topic": newslug}
                            )
                        except Exception:
                            print("[migration] shout topic error: " + newslug)
                session.commit()
            if newslug not in r:
                r.append(newslug)
        else:
            print("[migration] ignored topic slug: \n%r" % tpc["slug"])
            # raise Exception
    return r


async def content_ratings_to_reactions(entry, slug):
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
                        "shout": slug,
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
                    # shout_dict['ratings'].append(reaction_dict)

            session.commit()
    except Exception:
        raise Exception("[migration] content_item.ratings error: \n%r" % content_rating)
