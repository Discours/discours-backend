''' cmd managed migration '''
import json
from migration.export import export_email_subscriptions, export_mdx, export_slug
from migration.tables.users import migrate as migrateUser
from migration.tables.users import migrate_2stage as migrateUser_2stage
from migration.tables.content_items import get_shout_slug, migrate as migrateShout
from migration.tables.topics import migrate as migrateTopic
from migration.tables.comments import migrate as migrateComment
from migration.tables.comments import migrate_2stage as migrateComment_2stage

OLD_DATE = '2016-03-05 22:22:00.350000'

def users_handle(storage):
	''' migrating users first '''
	counter = 0
	id_map = {}
	print('[migration] migrating %d users' %(len(storage['users']['data'])))
	for entry in storage['users']['data']:
		oid = entry['_id']
		user = migrateUser(entry)
		storage['users']['by_oid'][oid] = user # full
		del user['password']
		del user['notifications']
		del user['emailConfirmed']
		del user['username']
		del user['email']
		storage['users']['by_slug'][user['slug']] = user # public
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
	print( '[migration] ' + str(counter) + ' topics migrated')
	print( '[migration] ' + str(len(storage['topics']['by_oid'].values())) + ' topics by oid' )
	print( '[migration] ' + str(len(storage['topics']['by_slug'].values())) + ' topics by slug' )
	# raise Exception
	return storage

def shouts_handle(storage):
	''' migrating content items one by one '''
	counter = 0
	discours_author = 0
	pub_counter = 0
	for entry in storage['shouts']['data']:
		oid = entry['_id']
		# slug
		slug = get_shout_slug(entry)

		 # single slug mode
		if '-' in sys.argv and slug not in sys.argv: continue

		# migrate
		shout = migrateShout(entry, storage)
		storage['shouts']['by_oid'][entry['_id']] = shout
		storage['shouts']['by_slug'][shout['slug']] = shout
		# shouts.topics
		if not shout['topics']: print('[migration] no topics!')

		# wuth author
		author = shout['authors'][0].slug
		if author =='discours': discours_author += 1
		# print('[migration] ' + shout['slug'] + ' with author ' + author)

		if entry.get('published'):
			export_mdx(shout)
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
	for oldcomment in storage['comments']['data']:
		comment = migrateComment(oldcomment, storage)
		if not comment:
			print('[migration] comment ignored \n%r\n' % oldcomment)
			ignored_counter += 1
			continue
		id = comment.get('id')
		oid = comment.get('oid')
		id_map[oid] = id

	for comment in storage['comments']['data']: migrateComment_2stage(comment, id_map)
	print('[migration] ' + str(len(id_map)) + ' comments migrated')
	print('[migration] ' + str(ignored_counter) + ' comments ignored')
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

def all_handle(storage):
	print('[migration] everything!')
	users_handle(storage)
	topics_handle(storage)
	shouts_handle(storage)
	comments_handle(storage)
	export_email_subscriptions()
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
		'comments': {
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
		print('[migration] ' + str(len(users_data)) + ' users loaded')
		tags_data = json.loads(open('migration/data/tags.json').read())
		storage['topics']['tags'] = tags_data
		print('[migration] ' + str(len(tags_data)) + ' tags loaded')
		cats_data = json.loads(open('migration/data/content_item_categories.json').read())
		storage['topics']['cats'] = cats_data
		print('[migration] ' + str(len(cats_data)) + ' cats loaded')
		comments_data = json.loads(open('migration/data/comments.json').read())
		storage['comments']['data'] = comments_data
		print('[migration] ' + str(len(comments_data)) + ' comments loaded')
		content_data = json.loads(open('migration/data/content_items.json').read())
		storage['shouts']['data'] = content_data
		print('[migration] ' + str(len(content_data)) + ' content items loaded')
		# fill out storage
		for x in users_data: 
			storage['users']['by_oid'][x['_id']] = x
			# storage['users']['by_slug'][x['slug']] = x 
		# no user.slug yet
		print('[migration] ' + str(len(storage['users']['by_oid'].keys())) + ' users by oid')
		for x in tags_data: 
			storage['topics']['by_oid'][x['_id']] = x
			storage['topics']['by_slug'][x['slug']] = x
		for x in cats_data:
			storage['topics']['by_oid'][x['_id']] = x
			storage['topics']['by_slug'][x['slug']] = x
		print('[migration] ' + str(len(storage['topics']['by_slug'].keys())) + ' topics by slug')
		for item in content_data:
			slug = get_shout_slug(item)
			storage['content_items']['by_slug'][slug] = item
			storage['content_items']['by_oid'][item['_id']] = item
		print('[migration] ' + str(len(content_data)) + ' content items')
		for x in comments_data:
			storage['comments']['by_oid'][x['_id']] = x
			cid = x['contentItem']
			storage['comments']['by_content'][cid] = x
			ci = storage['content_items']['by_oid'].get(cid, {})
			if 'slug' in ci: storage['comments']['by_slug'][ci['slug']] = x
		print('[migration] ' + str(len(storage['comments']['by_content'].keys())) + ' with comments')
	except Exception as e: raise e
	storage['users']['data'] = users_data
	storage['topics']['tags'] = tags_data
	storage['topics']['cats'] = cats_data
	storage['shouts']['data'] = content_data
	storage['comments']['data'] = comments_data
	return storage

if __name__ == '__main__':
	import sys
	if len(sys.argv) > 1:
		cmd = sys.argv[1]
		print('[migration] command: ' + cmd)
		if cmd == 'bson': 
			bson_handle()
		else:
			storage = data_load()
			if cmd == '-': export_one(sys.argv[2], storage)
			else: all_handle(storage)
			
	else:
		print('usage: python migrate.py bson')
		print('.. \t- <slug>')
		print('.. \tall')
