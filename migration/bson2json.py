import bson
import datetime
import json
import importlib

import DateTimeEncoder from utils

def json_tables():
    print('creating json files at data/')
    data = {
        "content_items": [],
        "content_item_categories": [],
        "tags": [],
        "email_subscriptions": [],
        "users": [],
        "comments": []
    }
    for table in data.keys():
        lc = []
        with open('data/'+table+'.bson', 'rb') as f:
            bs = f.read()
            base = 0
            while base < len(bs):
                base, d = bson.decode_document(bs, base)
                lc.append(d)
            data[table] = lc
            open('data/'+table+'.json', 'w').write(json.dumps(lc,cls=DateTimeEncoder))
    return data

