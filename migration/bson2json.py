import os
import bson
import json

from migration.utils import DateTimeEncoder

def json_tables():
	print('[migration] unpack bson to migration/data/*.json')
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
		with open('migration/data/'+table+'.bson', 'rb') as f:
			bs = f.read()
			f.close()
			base = 0
			while base < len(bs):
				base, d = bson.decode_document(bs, base)
				lc.append(d)
			data[table] = lc
			open(os.getcwd() + '/dump/discours/'+table+'.json', 'w').write(json.dumps(lc,cls=DateTimeEncoder))

