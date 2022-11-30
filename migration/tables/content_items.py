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
from orm.topic import TopicFollower, Topic
# from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage
import re

OLD_DATE = "2016-03-05 22:22:00.350000"
ts = datetime.now(tz=timezone.utc)
type2layout = {
    "Article": "article",
    "Literature": "literature",
    "Music": "audio",
    "Video": "video",
    "Image": "image",
}

anondict = {"slug": "anonymous", "id": 1, "name": "Аноним"}


def get_shout_slug(entry):
    slug = entry.get("slug", "")
    if not slug:
        for friend in entry.get("friendlySlugs", []):
            slug = friend.get("slug", "")
            if slug:
                break
    slug = re.sub('[^0-9a-zA-Z]+', '-', slug)
    return slug


def create_author_from_app(app):
    try:
        with local_session() as session:
            # check if email is used
            user = session.query(User).where(User.email == app['email']).first()
            if not user:
                name = app.get('name')
                slug = translit(name, "ru", reversed=True).lower()
                slug = re.sub('[^0-9a-zA-Z]+', '-', slug)
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
            userdata = User.default_user.dict()  # anonymous
    except Exception as e:
        print(app)
        raise e
    return userdata


async def create_shout(shout_dict, user):
    s = Shout.create(**shout_dict)
    with local_session() as session:
        srf = session.query(ShoutReactionsFollower).where(
            ShoutReactionsFollower.shout == s.id
        ).filter(
            ShoutReactionsFollower.follower == user.id
        ).first()
        if not srf:
            srf = ShoutReactionsFollower.create(shout=s.id, follower=user.id, auto=True)
            session.add(srf)
        session.commit()
    return s


def get_userdata(entry, storage):
    user_oid = entry.get("createdBy", "")
    userdata = None
    app = entry.get("application")
    if app:
        userdata = create_author_from_app(app) or anondict
    else:
        userdata = storage["users"]["by_oid"].get(user_oid) or anondict
    slug = userdata.get("slug")
    slug = re.sub('[^0-9a-zA-Z]+', '-', slug)
    userdata["slug"] = slug
    return userdata, user_oid


async def migrate(entry, storage):
    userdata, user_oid = get_userdata(entry, storage)
    user = await get_user(userdata, storage, user_oid)
    r = {
        "layout": type2layout[entry["type"]],
        "title": entry["title"],
        "authors": [userdata["slug"], ],
        "slug": get_shout_slug(entry),
        "cover": (
            "https://assets.discours.io/unsafe/1600x/" +
            entry["thumborId"] if entry.get("thumborId") else entry.get("image", {}).get("url")
        ),
        "visibility": "public" if entry.get("published") else "authors",
        "publishedAt": date_parse(entry.get("publishedAt")) if entry.get("published") else None,
        "deletedAt": date_parse(entry.get("deletedAt")) if entry.get("deletedAt") else None,
        "createdAt": date_parse(entry.get("createdAt", OLD_DATE)),
        "updatedAt": date_parse(entry["updatedAt"]) if "updatedAt" in entry else ts,
        "topics": await add_topics_follower(entry, storage, user),
        "body": extract_html(entry)
    }

    # main topic patch
    r['mainTopic'] = r['topics'][0]

    # published author auto-confirm
    if entry.get("published"):
        with local_session() as session:
            # update user.emailConfirmed if published
            author = session.query(User).where(User.slug == userdata["slug"]).first()
            author.emailConfirmed = True
            session.add(author)
            session.commit()

    # media
    media = extract_media(entry)
    r["media"] = json.dumps(media, ensure_ascii=True) if media else None

    # ----------------------------------- copy
    shout_dict = r.copy()

    # user
    shout_dict["authors"] = [user, ]
    del shout_dict["topics"]
    try:
        # save shout to db
        shout_dict["oid"] = entry.get("_id", "")
        shout = await create_shout(shout_dict, user)
    except IntegrityError as e:
        print('[migration] create_shout integrity error', e)
        shout = await resolve_create_shout(shout_dict, userdata["slug"])
    except Exception as e:
        raise Exception(e)

    # udpate data
    shout_dict = shout.dict()
    shout_dict["authors"] = [user.dict(), ]

    # shout topics aftermath
    shout_dict["topics"] = await topics_aftermath(r, storage)

    # content_item ratings to reactions
    await content_ratings_to_reactions(entry, shout_dict["slug"])

    # shout views
    await ViewedStorage.increment(shout_dict["slug"], amount=entry.get("views", 1))
    # del shout_dict['ratings']

    storage["shouts"]["by_oid"][entry["_id"]] = shout_dict
    storage["shouts"]["by_slug"][shout_dict["slug"]] = shout_dict
    return shout_dict


async def add_topics_follower(entry, storage, user):
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
        for tpcslug in topics:
            try:
                tpc = session.query(Topic).where(Topic.slug == tpcslug).first()
                tf = session.query(
                    TopicFollower
                ).where(
                    TopicFollower.follower == user.id
                ).filter(
                    TopicFollower.topic == tpc.id
                ).first()
                if not tf:
                    tf = TopicFollower.create(
                        topic=tpc.id,
                        follower=user.id,
                        auto=True
                    )
                    session.add(tf)
                    session.commit()
            except IntegrityError:
                print('[migration.shout] hidden by topic ' + tpc.slug)
    # main topic
    maintopic = storage["replacements"].get(topics_by_oid.get(category, {}).get("slug"))
    if maintopic in ttt:
        ttt.remove(maintopic)
    ttt.insert(0, maintopic)
    return ttt


async def get_user(userdata, storage, oid):
    user = None
    with local_session() as session:
        uid = userdata.get("id")
        if uid:
            user = session.query(User).filter(User.id == uid).first()
        elif userdata:
            try:
                slug = userdata["slug"].lower().strip()
                slug = re.sub('[^0-9a-zA-Z]+', '-', slug)
                userdata["slug"] = slug
                user = User.create(**userdata)
                session.add(user)
                session.commit()
            except IntegrityError:
                print("[migration] user creating with slug %s" % userdata["slug"])
                print("[migration] from userdata: %r" % userdata)
                raise Exception("[migration] cannot create user in content_items.get_user()")
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
        return s


async def topics_aftermath(entry, storage):
    r = []
    for tpc in filter(lambda x: bool(x), entry["topics"]):
        oldslug = tpc
        newslug = storage["replacements"].get(oldslug, oldslug)

        if newslug:
            with local_session() as session:
                shout = session.query(Shout).where(Shout.slug == entry["slug"]).one()
                new_topic = session.query(Topic).where(Topic.slug == newslug).one()

                shout_topic_old = (
                    session.query(ShoutTopic)
                    .join(Shout)
                    .join(Topic)
                    .filter(Shout.slug == entry["slug"])
                    .filter(Topic.slug == oldslug)
                    .first()
                )
                if shout_topic_old:
                    shout_topic_old.update({"topic": new_topic.id})
                else:
                    shout_topic_new = (
                        session.query(ShoutTopic)
                        .join(Shout)
                        .join(Topic)
                        .filter(Shout.slug == entry["slug"])
                        .filter(Topic.slug == newslug)
                        .first()
                    )
                    if not shout_topic_new:
                        try:
                            ShoutTopic.create(
                                **{"shout": shout.id, "topic": new_topic.id}
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
                ) or User.default_user
                shout = session.query(Shout).where(Shout.slug == slug).first()
                cts = content_rating.get("createdAt")
                reaction_dict = {
                    "createdAt": date_parse(cts) if cts else None,
                    "kind": ReactionKind.LIKE
                    if content_rating["value"] > 0
                    else ReactionKind.DISLIKE,
                    "createdBy": rater.id,
                    "shout": shout.id
                }
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
                    session.add(reaction)
                else:
                    rea = Reaction.create(**reaction_dict)
                    session.add(rea)
                    # await ReactedStorage.react(rea)
                # shout_dict['ratings'].append(reaction_dict)

            session.commit()
    except Exception:
        print("[migration] content_item.ratings error: \n%r" % content_rating)
