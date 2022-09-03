import os
import bson
import json

from .utils import DateTimeEncoder


def json_tables():
    print("[migration] unpack dump/discours/*.bson to migration/data/*.json")
    data = {
        "content_items": [],
        "content_item_categories": [],
        "tags": [],
        "email_subscriptions": [],
        "users": [],
        "comments": [],
    }
    for table in data.keys():
        lc = []
        with open("dump/discours/" + table + ".bson", "rb") as f:
            bs = f.read()
            f.close()
            base = 0
            while base < len(bs):
                base, d = bson.decode_document(bs, base)
                lc.append(d)
            data[table] = lc
            open(os.getcwd() + "/migration/data/" + table + ".json", "w").write(
                json.dumps(lc, cls=DateTimeEncoder)
            )
