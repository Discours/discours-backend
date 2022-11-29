from datetime import datetime, timezone

from dateutil.parser import parse as date_parse

from base.orm import local_session
from migration.html2text import html2text
from orm.reaction import Reaction, ReactionKind
from orm.shout import ShoutReactionsFollower, Shout
from orm.topic import TopicFollower, Topic
from orm.user import User

ts = datetime.now(tz=timezone.utc)


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
    reaction_dict = {
        "createdAt": (
            ts if not entry.get("createdAt") else date_parse(entry.get("createdAt"))
        ),
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
        with local_session() as session:
            author = session.query(User).filter(User.oid == entry["createdBy"]).first()
            shout_dict = storage["shouts"]["by_oid"][shout_oid]
            if shout_dict:
                shout = session.query(
                    Shout
                ).where(Shout.slug == shout_dict["slug"]).one()


                reaction_dict["shout_id"] = shout.id
                reaction_dict["createdBy"] = author.id if author else 1
                reaction_dict["kind"] = ReactionKind.COMMENT

                # creating reaction from old comment
                reaction = Reaction.create(**reaction_dict)
                session.add(reaction)

                # creating shout's reactions following for reaction author
                following1 = session.query(
                    ShoutReactionsFollower
                ).join(
                    User
                ).join(
                    Shout
                ).where(
                    User.id == reaction_dict["createdBy"]
                ).filter(
                    ShoutReactionsFollower.shout_id == reaction.shout_id
                ).first()

                if not following1:
                    following1 = ShoutReactionsFollower.create(
                        follower_id=reaction_dict["createdBy"],
                        shout_id=reaction.shout_id,
                        auto=True
                    )
                    session.add(following1)

                # creating topics followings for reaction author
                for t in shout_dict["topics"]:
                    tf = session.query(
                        TopicFollower
                    ).join(
                        Topic
                    ).where(
                        TopicFollower.follower_id == reaction_dict["createdBy"]
                    ).filter(
                        Topic.slug == t
                    ).first()

                    if not tf:
                        topic = session.query(
                            Topic
                        ).where(Topic.slug == t).one()

                        topic_following = TopicFollower.create(
                            follower_id=reaction_dict["createdBy"],
                            topic_id=topic.id,
                            auto=True
                        )
                        session.add(topic_following)

                reaction_dict["id"] = reaction.id
                for comment_rating_old in entry.get("ratings", []):
                    rater = (
                        session.query(User)
                            .filter(User.oid == comment_rating_old["createdBy"])
                            .first()
                    )
                    re_reaction_dict = {
                        "shout_id": reaction_dict["shout_id"],
                        "replyTo": reaction.id,
                        "kind": ReactionKind.LIKE
                        if comment_rating_old["value"] > 0
                        else ReactionKind.DISLIKE,
                        "createdBy": rater.id if rater else 1,
                    }
                    cts = comment_rating_old.get("createdAt")
                    if cts:
                        re_reaction_dict["createdAt"] = date_parse(cts)
                    try:
                        # creating reaction from old rating
                        rr = Reaction.create(**re_reaction_dict)
                        following2 = session.query(
                            ShoutReactionsFollower
                        ).where(
                            ShoutReactionsFollower.follower_id == re_reaction_dict['createdBy']
                        ).filter(
                            ShoutReactionsFollower.shout_id == rr.shout_id
                        ).first()
                        if not following2:
                            following2 = ShoutReactionsFollower.create(
                                follower_id=re_reaction_dict['createdBy'],
                                shout_id=rr.shout_id,
                                auto=True
                            )
                            session.add(following2)
                        session.add(rr)

                    except Exception as e:
                        print("[migration] comment rating error: %r" % re_reaction_dict)
                        raise e
                session.commit()
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
        session.add(comment)

        srf = session.query(ShoutReactionsFollower).where(
            ShoutReactionsFollower.shout_id == comment.shout_id
        ).filter(
            ShoutReactionsFollower.follower_id == comment.createdBy
        ).first()

        if not srf:
            srf = ShoutReactionsFollower.create(shout_id=comment.shout_id, follower_id=comment.createdBy, auto=True)
            session.add(srf)

        session.commit()
    if not rr["body"]:
        raise Exception(rr)
