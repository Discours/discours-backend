''' cmd managed migration '''
from datetime import datetime
import json
import subprocess
import sys

from click import prompt
# from migration.export import export_email_subscriptions
from migration.export import export_mdx, export_slug
from migration.tables.users import migrate as migrateUser
from migration.tables.users import migrate_2stage as migrateUser_2stage
from migration.tables.content_items import get_shout_slug, migrate as migrateShout
from migration.tables.topics import migrate as migrateTopic
from migration.tables.comments import migrate as migrateComment
from migration.tables.comments import migrate_2stage as migrateComment_2stage
from orm.reaction import Reaction

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


def shouts_handle(storage, args):
	''' migrating content items one by one '''
	counter = 0
	discours_author = 0
	pub_counter = 0
	for entry in storage['shouts']['data']:
		# slug
		slug = get_shout_slug(entry)

		 # single slug mode
		if '-' in args and slug not in args: continue

		# migrate
		shout = migrateShout(entry, storage)
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

	print('[migration] ' + str(counter) + ' content items were migrated')
	print('[migration] ' + str(pub_counter) + ' have been published')
	print('[migration] ' + str(discours_author) + ' authored by @discours')
	return storage


def comments_handle(storage):
	id_map = {}
	ignored_counter = 0
	missed_shouts = {}
	for oldcomment in storage['reactions']['data']:
		if not oldcomment.get('deleted'):
			reaction = migrateComment(oldcomment, storage)
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


def all_handle(storage, args):
	print('[migration] handle everything')
	users_handle(storage)
	topics_handle(storage)
	shouts_handle(storage, args)
	comments_handle(storage)
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
		print('[migration] ' + str(len(users_data)) + ' users ')
		tags_data = json.loads(open('migration/data/tags.json').read())
		storage['topics']['tags'] = tags_data
		print('[migration] ' + str(len(tags_data)) + ' tags ')
		cats_data = json.loads(
			open('migration/data/content_item_categories.json').read())
		storage['topics']['cats'] = cats_data
		print('[migration] ' + str(len(cats_data)) + ' cats ')
		comments_data = json.loads(open('migration/data/comments.json').read())
		storage['reactions']['data'] = comments_data
		print('[migration] ' + str(len(comments_data)) + ' comments ')
		content_data = json.loads(open('migration/data/content_items.json').read())
		storage['shouts']['data'] = content_data
		print('[migration] ' + str(len(content_data)) + ' content items ')
		# fill out storage
		for x in users_data:
			storage['users']['by_oid'][x['_id']] = x
			# storage['users']['by_slug'][x['slug']] = x
		# no user.slug yet
		print('[migration] ' + str(len(storage['users']
			  ['by_oid'].keys())) + ' users by oid')
		for x in tags_data:
			storage['topics']['by_oid'][x['_id']] = x
			storage['topics']['by_slug'][x['slug']] = x
		for x in cats_data:
			storage['topics']['by_oid'][x['_id']] = x
			storage['topics']['by_slug'][x['slug']] = x
		print('[migration] ' + str(len(storage['topics']
			  ['by_slug'].keys())) + ' topics by slug')
		for item in content_data:
			slug = get_shout_slug(item)
			storage['content_items']['by_slug'][slug] = item
			storage['content_items']['by_oid'][item['_id']] = item
		print('[migration] ' + str(len(content_data)) + ' content items')
		for x in comments_data:
			storage['reactions']['by_oid'][x['_id']] = x
			cid = x['contentItem']
			storage['reactions']['by_content'][cid] = x
			ci = storage['content_items']['by_oid'].get(cid, {})
			if 'slug' in ci: storage['reactions']['by_slug'][ci['slug']] = x
		print('[migration] ' + str(len(storage['reactions']
			  ['by_content'].keys())) + ' with comments')
	except Exception as e: raise e
	storage['users']['data'] = users_data
	storage['topics']['tags'] = tags_data
	storage['topics']['cats'] = cats_data
	storage['shouts']['data'] = content_data
	storage['reactions']['data'] = comments_data
	return storage


def mongo_download(url):
	print('[migration] mongodb url: ' + url)
	open('migration/data/mongodb.url', 'w').write(url)
	logname = 'migration/data/mongo-' + TODAY + '.log'
	subprocess.call([
		'mongodump',
		'--uri', url,
		'--forceTableScan',
	], open(logname, 'w'))


def create_pgdump():
	# pg_dump -d discoursio > 20220714-pgdump.sql
	subprocess.Popen(
		[ 'pg_dump', 'postgres://localhost:5432/discoursio', '-f', 'migration/data/' + TODAY + '-pgdump.log'], 
		stderr = subprocess.STDOUT
	)
	# scp 20220714-pgdump.sql root@build.discours.io:/root/discours-backend/.
	subprocess.call([
		'scp',
		'migration/data/' + TODAY + '-pgdump.sql',
		'root@build.discours.io:/root/discours-backend/.'
	])
	print('[migration] pg_dump up')


def handle_auto():
	print('[migration] no command given, auto mode')
	import os
	if os.path.isfile('migration/data/mongo-' + TODAY + '.log'):
		url=open('migration/data/mongodb.url', 'r').read()
		if not url:
			url=prompt('provide mongo url:')
			open('migration/data/mongodb.url', 'w').write(url)
		mongo_download(url)
	bson_handle()
	all_handle(data_load(), sys.argv)
	create_pgdump()

def migrate():
	import sys

	if len(sys.argv) > 1:
		cmd=sys.argv[1]
		print('[migration] command: ' + cmd)
		if cmd == 'mongodb':
			mongo_download(sys.argv[2])
		elif cmd == 'bson':
			bson_handle()
		else:
			storage=data_load()
			if cmd == '-': export_one(sys.argv[2], storage)
			else: all_handle(storage, sys.argv)
	elif len(sys.argv) == 1:
		handle_auto()
	else:
		print('[migration] usage: python ./migration <command>')
		print('[migration] commands: mongodb, bson, all, all mdx, - <slug>')

if __name__ == '__main__':
	migrate()
