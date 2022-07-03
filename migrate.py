''' cmd managed migration '''
import json
import frontmatter
from migration.extract import extract
from migration.tables.users import migrate as migrateUser
from migration.tables.users import migrate_2stage as migrateUser_2stage
from migration.tables.users import migrate_email_subscription
from migration.tables.content_items import get_metadata, migrate as migrateShout
from migration.tables.content_item_categories import migrate as migrateCategory
from migration.tables.tags import migrate as migrateTag
from migration.tables.comments import migrate as migrateComment
from migration.tables.comments import migrate_2stage as migrateComment_2stage
from migration.utils import DateTimeEncoder
from orm import Community, Topic
from dateutil.parser import parse as date_parse

from orm.base import local_session
from orm import User

OLD_DATE = '2016-03-05 22:22:00.350000'

def users(users_by_oid, users_by_slug, users_data):
	''' migrating users first '''
	# limiting
	limit = len(users_data)
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('[migration] %d users...' % limit)
	counter = 0
	id_map = {}
	for entry in users_data:
		oid = entry['_id']
		user = migrateUser(entry)
		users_by_oid[oid] = user # full
		del user['password']
		del user['notifications']
		# del user['oauth']
		del user['emailConfirmed']
		del user['username']
		del user['email']
		users_by_slug[user['slug']] = user # public
		id_map[user['old_id']] = user['slug']
		counter += 1
	# print(' - * - stage 2 users migration - * -')
	ce = 0
	for entry in users_data:
		ce += migrateUser_2stage(entry, id_map)
	# print(str(len(users_by_slug.items())) + ' users migrated')
	print('[migration] %d user ratings errors' % ce)
	#try:
	#	open('migration/data/users.old_id.json', 'w').write(json.dumps(users_by_oid, cls=DateTimeEncoder))  # NOTE: by old_id
	#	open('migration/data/users.slug.json', 'w').write(json.dumps(users_by_slug, cls=DateTimeEncoder))  # NOTE: by slug
	#except Exception:
	#	print('json dump error')
	#	# print(users_by_oid)


def topics(export_topics, topics_by_slug, topics_by_oid, cats_data, tags_data):
	''' topics from categories and tags '''
	# limiting
	limit = len(cats_data) + len(tags_data)
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('[migration] %d topics...' % limit)
	counter = 0
	retopics = json.loads(open('migration/tables/replacements.json').read())
	topicslugs_by_oid = {}
	for tag in tags_data:
		topicslugs_by_oid[tag['_id']] = tag['slug']
		oldid = tag['_id']
		tag['slug'] = retopics.get(tag['slug'], tag['slug'])
		topic = migrateTag(tag, topics_by_oid)
		topics_by_oid[oldid] = topic
		topics_by_slug[topic['slug']] = topic
		counter += 1
	for cat in cats_data:
		topicslugs_by_oid[cat['_id']] = cat['slug']
		if not cat.get('hidden'):
			oldid = cat['_id']
			cat['slug'] = retopics.get(cat['slug'], cat['slug'])
			try: topic = migrateCategory(cat, topics_by_oid)
			except Exception as e: raise e
			topics_by_oid[oldid] = topic
			topic['slug'] = retopics.get(topic['slug'], topic['slug'])
			topics_by_slug[topic['slug']] = topic
			counter += 1
	for oid, oslug in topicslugs_by_oid.items():
		if topics_by_slug.get(oslug):
			topics_by_oid[oid] = topics_by_slug.get(retopics.get(oslug, oslug))
	print( '[migration] ' + str(len(topics_by_oid.values())) + ' topics by oid' )
	print( '[migration] ' + str(len(topics_by_slug.values())) + ' topics by slug' )
	#replacements = {} # json.loads(open('migration/tables/replacements.json').read())
	#for t in topics_by_title.values():
	#	slug = replacements.get(t['slug'].strip()) or t['slug'].strip()
	#	topics_by_slug[slug] = t
	export_topics = topics_by_slug
	#for i in topicslugs:
	#	export_topics[i] = i
	#open('migration/tables/replacements2.json', 'w').write(json.dumps(export_topics,
	#													cls=DateTimeEncoder,
	#													indent=4,
	#													sort_keys=True,
	#													ensure_ascii=False))

def shouts(content_data, shouts_by_slug, shouts_by_oid):
	''' migrating content items one by one '''
	# limiting
	limit = len(content_data)
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('[migration] %d content items...' % limit)
	counter = 0
	discours_author = 0
	errored = []
	pub_counter = 0
	# limiting
	try: limit = int(sys.argv[2]) if len(sys.argv) > 2 else len(content_data)
	except ValueError:  limit = len(content_data)
	for entry in content_data[:limit]:
		if 'slug' in sys.argv and entry['slug'] not in sys.argv: continue
		try:
			shout, terrors = migrateShout(entry, users_by_oid, topics_by_oid)
			if entry.get('published'): pub_counter += 1
			author = shout['authors'][0]
			shout['authors'] = [ author.id, ]
			newtopics = []
			retopics = json.loads(open('migration/tables/replacements.json').read())
			for slug in shout['topics']:
				nt = retopics.get(slug, slug)
				if nt not in newtopics:
					newtopics.append(nt)
			shout['topics'] = newtopics
			shouts_by_slug[shout['slug']] = shout
			shouts_by_oid[entry['_id']] = shout
			line = str(counter+1) + ': ' + shout['slug'] + " @" + str(author.slug)
			counter += 1
			if author.slug == 'discours': discours_author += 1
			print(line)
			# open('./shouts.id.log', 'a').write(line + '\n')
		except Exception as e:
			# print(entry['_id'])
			errored.append(entry)
			raise e
	# print(te)
	# open('migration/data/shouts.old_id.json','w').write(json.dumps(shouts_by_oid, cls=DateTimeEncoder))
	# open('migration/data/shouts.slug.json','w').write(json.dumps(shouts_by_slug, cls=DateTimeEncoder))
	print('[migration] ' + str(counter) + ' content items were migrated')
	print('[migration] ' + str(pub_counter) + ' have been published')
	print('[migration] ' + str(discours_author) + ' authored by @discours')
	
def export_shouts(shouts_by_slug, export_articles, export_authors, content_dict):
	# update what was just migrated or load json again
	if len(export_authors.keys()) == 0:
		export_authors = json.loads(open('../src/data/authors.json').read())
		print('[migration] ' + str(len(export_authors.items())) + ' exported authors loaded')
	if len(export_articles.keys()) == 0:
		export_articles = json.loads(open('../src/data/articles.json').read())
		print('[migration] ' + str(len(export_articles.items())) + ' exported articles loaded')
	
	# limiting
	limit = 33
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('[migration] ' + 'exporting %d articles to json...' % limit)
	
	# filter 
	export_list = [i for i in shouts_by_slug.items() if i[1]['layout'] == 'article']
	export_list = sorted(export_list, key=lambda item: item[1]['createdAt'] or OLD_DATE, reverse=True)
	print('[migration] ' + str(len(export_list)) + ' filtered')
	export_list = export_list[:limit or len(export_list)]
	
	for (slug, article) in export_list:
		if article['layout'] == 'article':
			export_slug(slug, export_articles, export_authors, content_dict)
	
def export_body(article, content_dict):
	article['body'] = extract(article['body'], article['oid'])
	metadata = get_metadata(article)
	content = frontmatter.dumps(frontmatter.Post(article['body'], **metadata))
	open('../discoursio-web/content/' + article['slug'] + '.mdx', 'w').write(content)
	open('../discoursio-web/content/'+ article['slug'] + '.html', 'w').write(content_dict[article['old_id']]['body'])

def export_slug(slug, export_articles, export_authors, content_dict):
	print('[migration] ' + 'exporting %s ' % slug)
	if export_authors == {}: 
		export_authors = json.loads(open('../src/data/authors.json').read())
		print('[migration] ' + str(len(export_authors.items())) + ' exported authors loaded')
	if export_articles == {}:
		export_articles = json.loads(open('../src/data/articles.json').read())
		print('[migration] ' + str(len(export_articles.items())) + ' exported articles loaded')
		
	shout = shouts_by_slug.get(slug, False)
	assert shout, 'no data error'
	author = users_by_slug.get(shout['authors'][0]['slug'], None)
	export_authors.update({shout['authors'][0]['slug']: author})
	export_articles.update({shout['slug']: shout})
	export_body(shout, content_dict)
	comments([slug, ])

def comments(comments_data):
	id_map = {}
	for comment in comments_data:
		comment = migrateComment(comment, shouts_by_oid)
		if not comment:
			continue
		id = comment.get('id')
		old_id = comment.get('old_id')
		id_map[old_id] = id
	for comment in comments_data:
		migrateComment_2stage(comment, id_map)
	print('[migration] ' + str(len(id_map)) + ' comments exported')

def export_email_subscriptions():
	email_subscriptions_data = json.loads(open('migration/data/email_subscriptions.json').read())
	print('[migration] ' + str(len(email_subscriptions_data)) + ' email subscriptions loaded')
	for data in email_subscriptions_data:
		migrate_email_subscription(data)
	print('[migration] ' + str(len(email_subscriptions_data)) + ' email subscriptions exported')


def export_finish(export_articles = {}, export_authors = {}, export_topics = {}, export_comments = {}):
	open('../src/data/authors.json', 'w').write(json.dumps(export_authors,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print('[migration] ' + str(len(export_authors.items())) + ' authors exported')
	open('../src/data/topics.json', 'w').write(json.dumps(export_topics,
														cls=DateTimeEncoder,
														indent=4,
														sort_keys=True,
														ensure_ascii=False))
	print('[migration] ' + str(len(export_topics.keys())) + ' topics exported')
	
	open('../src/data/articles.json', 'w').write(json.dumps(export_articles,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print('[migration] ' + str(len(export_articles.items())) + ' articles exported')
	open('../src/data/comments.json', 'w').write(json.dumps(export_comments,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print('[migration] ' + str(len(export_comments.items())) + ' exported articles with comments')


if __name__ == '__main__':
	import sys

	if len(sys.argv) > 1:
			cmd = sys.argv[1]
			if cmd == "bson":
				# decode bson
				from migration import bson2json
				bson2json.json_tables()
			else:
				# preparing data
	
				# users
				users_data = json.loads(open('migration/data/users.json').read())
				print('[migration] ' + str(len(users_data)) + ' users loaded')
				users_by_oid = {}
				users_by_slug = {}
				user_id_map = {}
				with local_session() as session:
					users_list = session.query(User).all()
					for user in users_list:
						user_id_map[user.old_id] = user.id
						users_by_oid[user.old_id] = vars(user)
				# tags
				tags_data = json.loads(open('migration/data/tags.json').read())
				print('[migration] ' + str(len(tags_data)) + ' tags loaded')
				# cats
				cats_data = json.loads(open('migration/data/content_item_categories.json').read())
				print('[migration] ' + str(len(cats_data)) + ' cats loaded')
				topics_data = tags_data
				tags_data.extend(cats_data)
				oldtopics_by_oid = { x['_id']: x for x in topics_data }
				oldtopics_by_slug = { x['slug']: x for x in topics_data }
				topics_by_oid = {}
				topics_by_slug = {}

				# content
				content_data = json.loads(open('migration/data/content_items.json').read())
				content_dict = { x['_id']: x for x in content_data }
				print('[migration] ' + str(len(content_data)) + ' content items loaded')
				shouts_by_slug = {}
				shouts_by_oid = {}

				comments_data = json.loads(open('migration/data/comments.json').read())
				print('[migration] ' + str(len(comments_data)) + ' comments loaded')
				comments_by_post = {}
					# sort comments by old posts ids
				for old_comment in comments_data:
					cid = old_comment['contentItem']
					comments_by_post[cid] = comments_by_post.get(cid, [])
					if not old_comment.get('deletedAt', True):
						comments_by_post[cid].append(old_comment)
				print('[migration] ' + str(len(comments_by_post.keys())) + ' articles with comments')

				export_articles = {} # slug: shout
				export_authors = {} # slug: user
				export_comments = {} # shout-slug: comment[] (list)
				export_topics = {} # slug: topic

				##################### COMMANDS ##########################3

				if cmd == "users":
					users(users_by_oid, users_by_slug, users_data)
				elif cmd == "topics":
					topics(export_topics, topics_by_slug, topics_by_oid, cats_data, tags_data)
				elif cmd == "shouts":
					shouts(content_data, shouts_by_slug, shouts_by_oid) # NOTE: listens limit
				elif cmd == "comments":
					comments(comments_data)
				elif cmd == "export_shouts":
					export_shouts(shouts_by_slug, export_articles, export_authors, content_dict)
				elif cmd == "email_subscriptions":
					export_email_subscriptions()
				elif cmd == 'slug':
					export_slug(sys.argv[2], export_articles, export_authors, content_dict)
				elif cmd == "all":
					users(users_by_oid, users_by_slug, users_data)
					topics(export_topics, topics_by_slug, topics_by_oid, cats_data, tags_data)
					shouts(content_data, shouts_by_slug, shouts_by_oid)
					comments(comments_data)
					export_email_subscriptions()
				else:
					print('[migration] --- debug users, topics, shouts')
					users(users_by_oid, users_by_slug, users_data)
					topics(export_topics, topics_by_slug, topics_by_oid, cats_data, tags_data)
					shouts(content_data, shouts_by_slug, shouts_by_oid)
				#export_finish(export_articles, export_authors, export_topics, export_comments)
	else:
		print('usage: python migrate.py bson')
		print('.. \ttopics <limit>')
		print('.. \tusers <limit>')
		print('.. \tshouts <limit>')
		print('.. \texport_shouts <limit>')
		print('.. \tslug <slug>')
		print('.. \tall')
