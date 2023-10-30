# from base.orm import local_session

# from migration.extract import extract_md
# from migration.html2text import html2text
# from orm.reaction import Reaction, ReactionKind


# def migrate(entry, storage):
#     post_oid = entry["contentItem"]
#     print(post_oid)
#     shout_dict = storage["shouts"]["by_oid"].get(post_oid)
#     if shout_dict:
#         print(shout_dict["body"])
#         remark = {
#             "shout": shout_dict["id"],
#             "body": extract_md(html2text(entry["body"]), shout_dict),
#             "kind": ReactionKind.REMARK,
#         }
#
#         if entry.get("textBefore"):
#             remark["range"] = (
#                 str(shout_dict["body"].index(entry["textBefore"] or ""))
#                 + ":"
#                 + str(
#                     shout_dict["body"].index(entry["textAfter"] or "")
#                     + len(entry["textAfter"] or "")
#                 )
#             )
#
#         with local_session() as session:
#             rmrk = Reaction.create(**remark)
#             session.commit()
#             del rmrk["_sa_instance_state"]
#             return rmrk
#     return
