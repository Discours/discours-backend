from datetime import datetime, timezone

from dateutil.parser import parse as date_parse

from base.orm import local_session
from migration.html2text import html2text
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout, ShoutReactionsFollower
from orm.topic import TopicFollower
from orm.user import User

ts = datetime.now(tz=timezone.utc)


def auto_followers(session, topics, reaction_dict):
    # creating shout's reactions following for reaction author
    following1 = (
        session.query(ShoutReactionsFollower)
        .where(ShoutReactionsFollower.follower == reaction_dict["createdBy"])
        .filter(ShoutReactionsFollower.shout == reaction_dict["shout"])
        .first()
    )
    if not following1:
        following1 = ShoutReactionsFollower.create(
            follower=reaction_dict["createdBy"], shout=reaction_dict["shout"], auto=True
        )
        session.add(following1)
    # creating topics followings for reaction author
    for t in topics:
        tf = (
            session.query(TopicFollower)
            .where(TopicFollower.follower == reaction_dict["createdBy"])
            .filter(TopicFollower.topic == t['id'])
            .first()
        )
        if not tf:
            topic_following = TopicFollower.create(
                follower=reaction_dict["createdBy"], topic=t['id'], auto=True
            )
            session.add(topic_following)


def migrate_ratings(session, entry, reaction_dict):
    for comment_rating_old in entry.get("ratings", []):
        rater = session.query(User).filter(User.oid == comment_rating_old["createdBy"]).first()
        re_reaction_dict = {
            "shout": reaction_dict["shout"],
            "replyTo": reaction_dict["id"],
            "kind": ReactionKind.LIKE if comment_rating_old["value"] > 0 else ReactionKind.DISLIKE,
            "createdBy": rater.id if rater else 1,
        }
        cts = comment_rating_old.get("createdAt")
        if cts:
            re_reaction_dict["createdAt"] = date_parse(cts)
        try:
            # creating reaction from old rating
            rr = Reaction.create(**re_reaction_dict)
            following2 = (
                session.query(ShoutReactionsFollower)
                .where(ShoutReactionsFollower.follower == re_reaction_dict['createdBy'])
                .filter(ShoutReactionsFollower.shout == rr.shout)
                .first()
            )
            if not following2:
                following2 = ShoutReactionsFollower.create(
                    follower=re_reaction_dict['createdBy'], shout=rr.shout, auto=True
                )
                session.add(following2)
            session.add(rr)

        except Exception as e:
            print("[migration] comment rating error: %r" % re_reaction_dict)
            raise e
    session.commit()


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
    old_ts = entry.get("createdAt")
    reaction_dict = {
        "createdAt": (ts if not old_ts else date_parse(old_ts)),
        "body": html2text(entry.get("body", "")),
        "oid": entry["_id"],
    }
    shout_oid = entry.get("contentItem")
    if shout_oid not in storage["shouts"]["by_oid"]:
        if len(storage["shouts"]["by_oid"]) > 0:
            return shout_oid
        else:
            print("[migration] no shouts migrated yet")
            raise Exception
        return
    else:
        stage = "started"
        reaction = None
        with local_session() as session:
            author = session.query(User).filter(User.oid == entry["createdBy"]).first()
            old_shout = storage["shouts"]["by_oid"].get(shout_oid)
            if not old_shout:
                raise Exception("no old shout in storage")
            else:
                stage = "author and old id found"
                try:
                    shout = session.query(Shout).where(Shout.slug == old_shout["slug"]).one()
                    if shout:
                        reaction_dict["shout"] = shout.id
                        reaction_dict["createdBy"] = author.id if author else 1
                        reaction_dict["kind"] = ReactionKind.COMMENT

                        # creating reaction from old comment
                        reaction = Reaction.create(**reaction_dict)
                        session.add(reaction)
                        # session.commit()
                        stage = "new reaction commited"
                        reaction_dict = reaction.dict()
                        topics = [t.dict() for t in shout.topics]
                        auto_followers(session, topics, reaction_dict)

                        migrate_ratings(session, entry, reaction_dict)

                        return reaction
                except Exception as e:
                    print(e)
                    print(reaction)
                    raise Exception(stage)
    return


def migrate_2stage(old_comment, idmap):
    if old_comment.get('body'):
        new_id = idmap.get(old_comment.get('oid'))
        new_id = idmap.get(old_comment.get('_id'))
        if new_id:
            new_replyto_id = None
            old_replyto_id = old_comment.get("replyTo")
            if old_replyto_id:
                new_replyto_id = int(idmap.get(old_replyto_id, "0"))
            with local_session() as session:
                comment = session.query(Reaction).where(Reaction.id == new_id).first()
                try:
                    if new_replyto_id:
                        new_reply = (
                            session.query(Reaction).where(Reaction.id == new_replyto_id).first()
                        )
                        if not new_reply:
                            print(new_replyto_id)
                            raise Exception("cannot find reply by id!")
                        comment.replyTo = new_reply.id
                        session.add(comment)
                    srf = (
                        session.query(ShoutReactionsFollower)
                        .where(ShoutReactionsFollower.shout == comment.shout)
                        .filter(ShoutReactionsFollower.follower == comment.createdBy)
                        .first()
                    )
                    if not srf:
                        srf = ShoutReactionsFollower.create(
                            shout=comment.shout, follower=comment.createdBy, auto=True
                        )
                        session.add(srf)
                    session.commit()
                except Exception:
                    raise Exception("cannot find a comment by oldid")
