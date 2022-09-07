from datetime import datetime
from dateutil.parser import parse as date_parse
from orm import Reaction, User
from base.orm import local_session
from migration.html2text import html2text
from orm.reaction import ReactionKind
from services.stat.reacted import ReactedStorage

ts = datetime.now()


async def migrate(entry, storage):
    """
    {
      "_id": "hdtwS8fSyFLxXCgSC",
      "body": "<p>",
      "contentItem": "mnK8KsJHPRi8DrybQ",
      "createdBy": "bMFPuyNg6qAD2mhXe",
      "thread": "01/",
      "createdAt": "2016-04-19 04:33:53+00:00",
      "ratings": [
            { "createdBy": "AqmRukvRiExNpAe8C", "value": 1 },
            { "createdBy": "YdE76Wth3yqymKEu5", "value": 1 }
      ],
      "rating": 2,
      "updatedAt": "2020-05-27 19:22:57.091000+00:00",
      "updatedBy": "0"
    }

    ->

    type Reaction {
            id: Int!
            shout: Shout!
            createdAt: DateTime!
            createdBy: User!
            updatedAt: DateTime
            deletedAt: DateTime
            deletedBy: User
            range: String # full / 0:2340
            kind: ReactionKind!
            body: String
            replyTo: Reaction
            stat: Stat
            old_id: String
            old_thread: String
            }
    """
    reaction_dict = {}
    reaction_dict["createdAt"] = (
        ts if not entry.get("createdAt") else date_parse(entry.get("createdAt"))
    )
    print("[migration] reaction original date %r" % entry.get("createdAt"))
    # print('[migration] comment date %r ' % comment_dict['createdAt'])
    reaction_dict["body"] = html2text(entry.get("body", ""))
    reaction_dict["oid"] = entry["_id"]
    if entry.get("createdAt"):
        reaction_dict["createdAt"] = date_parse(entry.get("createdAt"))
    shout_oid = entry.get("contentItem")
    if shout_oid not in storage["shouts"]["by_oid"]:
        if len(storage["shouts"]["by_oid"]) > 0:
            return shout_oid
        else:
            print("[migration] no shouts migrated yet")
            raise Exception
        return
    else:
        with local_session() as session:
            author = session.query(User).filter(User.oid == entry["createdBy"]).first()
            shout_dict = storage["shouts"]["by_oid"][shout_oid]
            if shout_dict:
                reaction_dict["shout"] = shout_dict["slug"]
                reaction_dict["createdBy"] = author.slug if author else "discours"
                reaction_dict["kind"] = ReactionKind.COMMENT

                # creating reaction from old comment
                reaction = Reaction.create(**reaction_dict)
                await ReactedStorage.react(reaction)

                reaction_dict["id"] = reaction.id
                for comment_rating_old in entry.get("ratings", []):
                    rater = (
                        session.query(User)
                        .filter(User.oid == comment_rating_old["createdBy"])
                        .first()
                    )
                    reactedBy = (
                        rater
                        if rater
                        else session.query(User).filter(User.slug == "noname").first()
                    )
                    re_reaction_dict = {
                        "shout": reaction_dict["shout"],
                        "replyTo": reaction.id,
                        "kind": ReactionKind.LIKE
                        if comment_rating_old["value"] > 0
                        else ReactionKind.DISLIKE,
                        "createdBy": reactedBy.slug if reactedBy else "discours",
                    }
                    cts = comment_rating_old.get("createdAt")
                    if cts:
                        re_reaction_dict["createdAt"] = date_parse(cts)
                    try:
                        # creating reaction from old rating
                        rr = Reaction.create(**re_reaction_dict)
                        await ReactedStorage.react(rr)

                    except Exception as e:
                        print("[migration] comment rating error: %r" % re_reaction_dict)
                        raise e
            else:
                print(
                    "[migration] error: cannot find shout for comment %r"
                    % reaction_dict
                )
        return reaction


def migrate_2stage(rr, old_new_id):
    reply_oid = rr.get("replyTo")
    if not reply_oid:
        return
    new_id = old_new_id.get(rr.get("oid"))
    if not new_id:
        return
    with local_session() as session:
        comment = session.query(Reaction).filter(Reaction.id == new_id).first()
        comment.replyTo = old_new_id.get(reply_oid)
        comment.save()
        session.commit()
    if not rr["body"]:
        raise Exception(rr)
