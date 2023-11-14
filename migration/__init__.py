""" cmd managed migration """
import asyncio
import gc
import json
import sys
from datetime import datetime, timezone

import bs4

from migration.export import export_mdx
from migration.tables.comments import migrate as migrateComment
from migration.tables.comments import migrate_2stage as migrateComment_2stage
from migration.tables.content_items import get_shout_slug
from migration.tables.content_items import migrate as migrateShout

# from migration.tables.remarks import migrate as migrateRemark
from migration.tables.topics import migrate as migrateTopic
from migration.tables.users import migrate as migrateUser
from migration.tables.users import migrate_2stage as migrateUser_2stage
from migration.tables.users import post_migrate as users_post_migrate
from orm import init_tables
from orm.reaction import Reaction

TODAY = datetime.strftime(datetime.now(tz=timezone.utc), "%Y%m%d")
OLD_DATE = "2016-03-05 22:22:00.350000"


async def users_handle(storage):
    """migrating users first"""
    counter = 0
    id_map = {}
    print("[migration] migrating %d users" % (len(storage["users"]["data"])))
    for entry in storage["users"]["data"]:
        oid = entry["_id"]
        user = migrateUser(entry)
        storage["users"]["by_oid"][oid] = user  # full
        del user["password"]
        del user["emailConfirmed"]
        del user["username"]
        del user["email"]
        storage["users"]["by_slug"][user["slug"]] = user  # public
        id_map[user["oid"]] = user["slug"]
        counter += 1
    ce = 0
    for entry in storage["users"]["data"]:
        ce += migrateUser_2stage(entry, id_map)
    users_post_migrate()


async def topics_handle(storage):
    """topics from categories and tags"""
    counter = 0
    for t in storage["topics"]["tags"] + storage["topics"]["cats"]:
        if t["slug"] in storage["replacements"]:
            t["slug"] = storage["replacements"][t["slug"]]
            topic = migrateTopic(t)
            storage["topics"]["by_oid"][t["_id"]] = topic
            storage["topics"]["by_slug"][t["slug"]] = topic
            counter += 1
        else:
            print("[migration] topic " + t["slug"] + " ignored")
    for oldslug, newslug in storage["replacements"].items():
        if oldslug != newslug and oldslug in storage["topics"]["by_slug"]:
            oid = storage["topics"]["by_slug"][oldslug]["_id"]
            del storage["topics"]["by_slug"][oldslug]
            storage["topics"]["by_oid"][oid] = storage["topics"]["by_slug"][newslug]
    print("[migration] " + str(counter) + " topics migrated")
    print("[migration] " + str(len(storage["topics"]["by_oid"].values())) + " topics by oid")
    print("[migration] " + str(len(storage["topics"]["by_slug"].values())) + " topics by slug")


async def shouts_handle(storage, args):
    """migrating content items one by one"""
    counter = 0
    discours_author = 0
    anonymous_author = 0
    pub_counter = 0
    ignored = 0
    topics_dataset_bodies = []
    topics_dataset_tlist = []
    for entry in storage["shouts"]["data"]:
        gc.collect()
        # slug
        slug = get_shout_slug(entry)

        # single slug mode
        if "-" in args and slug not in args:
            continue

        # migrate
        shout_dict = await migrateShout(entry, storage)
        if shout_dict:
            storage["shouts"]["by_oid"][entry["_id"]] = shout_dict
            storage["shouts"]["by_slug"][shout_dict["slug"]] = shout_dict
            # shouts.topics
            if not shout_dict["topics"]:
                print("[migration] no topics!")

            # with author
            author = shout_dict["authors"][0]
            if author["slug"] == "discours":
                discours_author += 1
            if author["slug"] == "anonymous":
                anonymous_author += 1
            # print('[migration] ' + shout['slug'] + ' with author ' + author)

            if entry.get("published"):
                if "mdx" in args:
                    export_mdx(shout_dict)
                pub_counter += 1

            # print main counter
            counter += 1
            print(
                "[migration] shouts_handle %d: %s @%s"
                % ((counter + 1), shout_dict["slug"], author["slug"])
            )

            b = bs4.BeautifulSoup(shout_dict["body"], "html.parser")
            texts = [shout_dict["title"].lower().replace(r"[^а-яА-Яa-zA-Z]", "")]
            texts = texts + b.findAll(text=True)
            topics_dataset_bodies.append(" ".join([x.strip().lower() for x in texts]))
            topics_dataset_tlist.append(shout_dict["topics"])
        else:
            ignored += 1

    # np.savetxt('topics_dataset.csv', (topics_dataset_bodies, topics_dataset_tlist), delimiter=',
    # ', fmt='%s')

    print("[migration] " + str(counter) + " content items were migrated")
    print("[migration] " + str(pub_counter) + " have been published")
    print("[migration] " + str(discours_author) + " authored by @discours")
    print("[migration] " + str(anonymous_author) + " authored by @anonymous")


# async def remarks_handle(storage):
#     print("[migration] comments")
#     c = 0
#     for entry_remark in storage["remarks"]["data"]:
#         remark = await migrateRemark(entry_remark, storage)
#         c += 1
#     print("[migration] " + str(c) + " remarks migrated")


async def comments_handle(storage):
    print("[migration] comments")
    id_map = {}
    ignored_counter = 0
    missed_shouts = {}
    for oldcomment in storage["reactions"]["data"]:
        if not oldcomment.get("deleted"):
            reaction = await migrateComment(oldcomment, storage)
            if isinstance(reaction, str):
                missed_shouts[reaction] = oldcomment
            elif isinstance(reaction, Reaction):
                reaction = reaction.dict()
                rid = reaction["id"]
                oid = reaction["oid"]
                id_map[oid] = rid
            else:
                ignored_counter += 1

    for reaction in storage["reactions"]["data"]:
        migrateComment_2stage(reaction, id_map)
    print("[migration] " + str(len(id_map)) + " comments migrated")
    print("[migration] " + str(ignored_counter) + " comments ignored")
    print("[migration] " + str(len(missed_shouts.keys())) + " commented shouts missed")
    missed_counter = 0
    for missed in missed_shouts.values():
        missed_counter += len(missed)
    print("[migration] " + str(missed_counter) + " comments dropped")


async def all_handle(storage, args):
    print("[migration] handle everything")
    await users_handle(storage)
    await topics_handle(storage)
    print("[migration] users and topics are migrated")
    await shouts_handle(storage, args)
    # print("[migration] remarks...")
    # await remarks_handle(storage)
    print("[migration] migrating comments")
    await comments_handle(storage)
    # export_email_subscriptions()
    print("[migration] done!")


def data_load():
    storage = {
        "content_items": {
            "by_oid": {},
            "by_slug": {},
        },
        "shouts": {"by_oid": {}, "by_slug": {}, "data": []},
        "reactions": {"by_oid": {}, "by_slug": {}, "by_content": {}, "data": []},
        "topics": {
            "by_oid": {},
            "by_slug": {},
            "cats": [],
            "tags": [],
        },
        "remarks": {"data": []},
        "users": {"by_oid": {}, "by_slug": {}, "data": []},
        "replacements": json.loads(open("migration/tables/replacements.json").read()),
    }
    try:
        users_data = json.loads(open("migration/data/users.json").read())
        print("[migration.load] " + str(len(users_data)) + " users ")
        tags_data = json.loads(open("migration/data/tags.json").read())
        storage["topics"]["tags"] = tags_data
        print("[migration.load] " + str(len(tags_data)) + " tags ")
        cats_data = json.loads(open("migration/data/content_item_categories.json").read())
        storage["topics"]["cats"] = cats_data
        print("[migration.load] " + str(len(cats_data)) + " cats ")
        comments_data = json.loads(open("migration/data/comments.json").read())
        storage["reactions"]["data"] = comments_data
        print("[migration.load] " + str(len(comments_data)) + " comments ")
        content_data = json.loads(open("migration/data/content_items.json").read())
        storage["shouts"]["data"] = content_data
        print("[migration.load] " + str(len(content_data)) + " content items ")

        remarks_data = json.loads(open("migration/data/remarks.json").read())
        storage["remarks"]["data"] = remarks_data
        print("[migration.load] " + str(len(remarks_data)) + " remarks data ")

        # fill out storage
        for x in users_data:
            storage["users"]["by_oid"][x["_id"]] = x
            # storage['users']['by_slug'][x['slug']] = x
        # no user.slug yet
        print("[migration.load] " + str(len(storage["users"]["by_oid"].keys())) + " users by oid")
        for x in tags_data:
            storage["topics"]["by_oid"][x["_id"]] = x
            storage["topics"]["by_slug"][x["slug"]] = x
        for x in cats_data:
            storage["topics"]["by_oid"][x["_id"]] = x
            storage["topics"]["by_slug"][x["slug"]] = x
        print(
            "[migration.load] " + str(len(storage["topics"]["by_slug"].keys())) + " topics by slug"
        )
        for item in content_data:
            slug = get_shout_slug(item)
            storage["content_items"]["by_slug"][slug] = item
            storage["content_items"]["by_oid"][item["_id"]] = item
        print("[migration.load] " + str(len(content_data)) + " content items")
        for x in comments_data:
            storage["reactions"]["by_oid"][x["_id"]] = x
            cid = x["contentItem"]
            storage["reactions"]["by_content"][cid] = x
            ci = storage["content_items"]["by_oid"].get(cid, {})
            if "slug" in ci:
                storage["reactions"]["by_slug"][ci["slug"]] = x
        print(
            "[migration.load] "
            + str(len(storage["reactions"]["by_content"].keys()))
            + " with comments"
        )
        storage["users"]["data"] = users_data
        storage["topics"]["tags"] = tags_data
        storage["topics"]["cats"] = cats_data
        storage["shouts"]["data"] = content_data
        storage["reactions"]["data"] = comments_data
    except Exception as e:
        raise e
    return storage


async def handling_migration():
    init_tables()
    await all_handle(data_load(), sys.argv)


def process():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(handling_migration())


if __name__ == "__main__":
    process()
