''' cmd managed migration '''
import csv
import asyncio
from datetime import datetime
import json
import subprocess
import sys
import os
import bs4
import numpy as np
# from export import export_email_subscriptions
from .export import export_mdx, export_slug
from orm.reaction import Reaction
from .tables.users import migrate as migrateUser
from .tables.users import migrate_2stage as migrateUser_2stage
from .tables.content_items import get_shout_slug, migrate as migrateShout
from .tables.topics import migrate as migrateTopic
from .tables.comments import migrate as migrateComment
from .tables.comments import migrate_2stage as migrateComment_2stage

from settings import DB_URL


TODAY = datetime.strftime(datetime.now(), '%Y%m%d')

OLD_DATE = '2016-03-05 22:22:00.350000'


def users_handle(storage):
	''' migrating users first '''
	counter = 0
	id_map = {}
	print('[migration] migrating %d users' % (len(storage['users']['data'])))
	for entry in storage['users']['data']:
		oid = entry['_id']
		user = migrateUser(entry)
		storage['users']['by_oid'][oid] = user  # full
		del user['password']
		del user['notifications']
		del user['emailConfirmed']
		del user['username']
		del user['email']
		storage['users']['by_slug'][user['slug']] = user  # public
		id_map[user['oid']] = user['slug']
		counter += 1
	ce = 0
	for entry in storage['users']['data']:
		ce += migrateUser_2stage(entry, id_map)
	return storage


def topics_handle(storage):
	''' topics from categories and tags '''
	counter = 0
	for t in (storage['topics']['tags'] + storage['topics']['cats']):
		if t['slug'] in storage['replacements']:
			t['slug'] = storage['replacements'][t['slug']]
			topic = migrateTopic(t)
			storage['topics']['by_oid'][t['_id']] = topic
			storage['topics']['by_slug'][t['slug']] = topic
			counter += 1
		else:
			print('[migration] topic ' + t['slug'] + ' ignored')
	for oldslug, newslug in storage['replacements'].items():
		if oldslug != newslug and oldslug in storage['topics']['by_slug']:
			oid = storage['topics']['by_slug'][oldslug]['_id']
			del storage['topics']['by_slug'][oldslug]
			storage['topics']['by_oid'][oid] = storage['topics']['by_slug'][newslug]
	print('[migration] ' + str(counter) + ' topics migrated')
	print('[migration] ' + str(len(storage['topics']
		  ['by_oid'].values())) + ' topics by oid')
	print('[migration] ' + str(len(storage['topics']
		  ['by_slug'].values())) + ' topics by slug')
	# raise Exception
	return storage


async def shouts_handle(storage, args):
	''' migrating content items one by one '''
	counter = 0
	discours_author = 0
	pub_counter = 0
	topics_dataset_bodies = []
	topics_dataset_tlist = []
	for entry in storage['shouts']['data']:
		# slug
		slug = get_shout_slug(entry)

		 # single slug mode
		if '-' in args and slug not in args: continue

		# migrate
		shout = await migrateShout(entry, storage)
		storage['shouts']['by_oid'][entry['_id']] = shout
		storage['shouts']['by_slug'][shout['slug']] = shout
		# shouts.topics
		if not shout['topics']: print('[migration] no topics!')

		# wuth author
		author = shout['authors'][0].slug
		if author == 'discours': discours_author += 1
		# print('[migration] ' + shout['slug'] + ' with author ' + author)

		if entry.get('published'):
			if 'mdx' in args: export_mdx(shout)
			pub_counter += 1

		# print main counter
		counter += 1
		line = str(counter+1) + ': ' + shout['slug'] + " @" + author
		print(line)
		b = bs4.BeautifulSoup(shout['body'], 'html.parser')
		texts = []
		texts.append(shout['title'].lower().replace(r'[^а-яА-Яa-zA-Z]', ''))
		texts = b.findAll(text=True)
		topics_dataset_bodies.append(u" ".join([x.strip().lower() for x in texts]))
		topics_dataset_tlist.append(shout['topics'])
  
	np.savetxt('topics_dataset.csv', (topics_dataset_bodies, topics_dataset_tlist), delimiter=',', fmt='%s')

	print('[migration] ' + str(counter) + ' content items were migrated')
	print('[migration] ' + str(pub_counter) + ' have been published')
	print('[migration] ' + str(discours_author) + ' authored by @discours')
	return storage


async def comments_handle(storage):
	id_map = {}
	ignored_counter = 0
	missed_shouts = {}
	for oldcomment in storage['reactions']['data']:
		if not oldcomment.get('deleted'):
			reaction = await migrateComment(oldcomment, storage)
			if type(reaction) == str:
				missed_shouts[reaction] = oldcomment
			elif type(reaction) == Reaction:
				reaction = reaction.dict()
				id = reaction['id']
				oid = reaction['oid']
				id_map[oid] = id
			else:
				ignored_counter += 1

	for reaction in storage['reactions']['data']: migrateComment_2stage(
		reaction, id_map)
	print('[migration] ' + str(len(id_map)) + ' comments migrated')
	print('[migration] ' + str(ignored_counter) + ' comments ignored')
	print('[migration] ' + str(len(missed_shouts.keys())) +
		  ' commented shouts missed')
	missed_counter = 0
	for missed in missed_shouts.values():
		missed_counter += len(missed)
	print('[migration] ' + str(missed_counter) + ' comments dropped')
	return storage


def bson_handle():
	# decode bson # preparing data
	from migration import bson2json
	bson2json.json_tables()


def export_one(slug, storage):
	topics_handle(storage)
	users_handle(storage)
	shouts_handle(storage)
	export_slug(slug, storage)


async def all_handle(storage, args):
	print('[migration] handle everything')
	users_handle(storage)
	topics_handle(storage)
	await shouts_handle(storage, args)
	await comments_handle(storage)
	# export_email_subscriptions()
	print('[migration] done!')


def data_load():
	storage = {
		'content_items': {
			'by_oid': {},
			'by_slug': {},
		},
		'shouts': {
			'by_oid': {},
			'by_slug': {},
			'data': []
		},
		'reactions': {
			'by_oid': {},
			'by_slug': {},
			'by_content': {},
			'data':	[]
		},
		'topics': {
			'by_oid': {},
			'by_slug': {},
			'cats': [],
			'tags': [],
		},
		'users': {
			'by_oid': {},
			'by_slug': {},
			'data': []
		},
		'replacements': json.loads(open('migration/tables/replacements.json').read())
	}
	users_data = []
	tags_data = []
	cats_data = []
	comments_data = []
	content_data = []
	try:
		users_data = json.loads(open('migration/data/users.json').read())
		print('[migration.load] ' + str(len(users_data)) + ' users ')
		tags_data = json.loads(open('migration/data/tags.json').read())
		storage['topics']['tags'] = tags_data
		print('[migration.load] ' + str(len(tags_data)) + ' tags ')
		cats_data = json.loads(
			open('migration/data/content_item_categories.json').read())
		storage['topics']['cats'] = cats_data
		print('[migration.load] ' + str(len(cats_data)) + ' cats ')
		comments_data = json.loads(open('migration/data/comments.json').read())
		storage['reactions']['data'] = comments_data
		print('[migration.load] ' + str(len(comments_data)) + ' comments ')
		content_data = json.loads(open('migration/data/content_items.json').read())
		storage['shouts']['data'] = content_data
		print('[migration.load] ' + str(len(content_data)) + ' content items ')
		# fill out storage
		for x in users_data:
			storage['users']['by_oid'][x['_id']] = x
			# storage['users']['by_slug'][x['slug']] = x
		# no user.slug yet
		print('[migration.load] ' + str(len(storage['users']
			  ['by_oid'].keys())) + ' users by oid')
		for x in tags_data:
			storage['topics']['by_oid'][x['_id']] = x
			storage['topics']['by_slug'][x['slug']] = x
		for x in cats_data:
			storage['topics']['by_oid'][x['_id']] = x
			storage['topics']['by_slug'][x['slug']] = x
		print('[migration.load] ' + str(len(storage['topics']
			  ['by_slug'].keys())) + ' topics by slug')
		for item in content_data:
			slug = get_shout_slug(item)
			storage['content_items']['by_slug'][slug] = item
			storage['content_items']['by_oid'][item['_id']] = item
		print('[migration.load] ' + str(len(content_data)) + ' content items')
		for x in comments_data:
			storage['reactions']['by_oid'][x['_id']] = x
			cid = x['contentItem']
			storage['reactions']['by_content'][cid] = x
			ci = storage['content_items']['by_oid'].get(cid, {})
			if 'slug' in ci: storage['reactions']['by_slug'][ci['slug']] = x
		print('[migration.load] ' + str(len(storage['reactions']
			  ['by_content'].keys())) + ' with comments')
	except Exception as e: raise e
	storage['users']['data'] = users_data
	storage['topics']['tags'] = tags_data
	storage['topics']['cats'] = cats_data
	storage['shouts']['data'] = content_data
	storage['reactions']['data'] = comments_data
	return storage


def mongo_download(url):
	if not url: raise Exception('\n\nYou should set MONGODB_URL enviroment variable\n')
	print('[migration] mongodump ' + url)
	subprocess.call([
		'mongodump',
		'--uri', url + '/?authSource=admin',
		'--forceTableScan',
	], stderr = subprocess.STDOUT)


def create_pgdump():
	pgurl = DB_URL
	if not pgurl: raise Exception('\n\nYou should set DATABASE_URL enviroment variable\n')
	subprocess.call(
		[ 'pg_dump', pgurl, '-f', TODAY + '-pgdump.sql'], 
		stderr = subprocess.STDOUT
	)
	subprocess.call([
		'scp',
		TODAY + '-pgdump.sql',
		'root@build.discours.io:/root/.'
	])


async def handle_auto():
	print('[migration] no command given, auto mode')
	url = os.getenv('MONGODB_URL')
	if url: mongo_download(url)
	bson_handle()
	await all_handle(data_load(), sys.argv)
	create_pgdump()

async def main():
	if len(sys.argv) > 1:
		cmd=sys.argv[1]
		if type(cmd) == str: print('[migration] command: ' + cmd)
		await handle_auto()
	else:
		print('[migration] usage: python server.py migrate')

def migrate():
	loop = asyncio.get_event_loop()
	loop.run_until_complete(main())
 
if __name__ == '__main__':
	migrate()