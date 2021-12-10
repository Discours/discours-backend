''' cmd managed migration '''
import json
import pprint
import base64
import re
import frontmatter
from migration.tables.users import migrate as migrateUser
from migration.tables.users import migrate_2stage as migrateUser_2stage
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

print = pprint.pprint
IMG_REGEX = r"\!\[(.*?)\]\((data\:image\/(png|jpeg|jpg);base64\,(.*?))\)"
OLD_DATE = '2016-03-05 22:22:00.350000'


def extract_images(article):
	''' extract b64 encoded images from markdown in article body '''
	body = article['body']
	images = []
	matches = re.finditer(IMG_REGEX, body, re.IGNORECASE | re.MULTILINE)
	for i, match in enumerate(matches, start=1):
		ext = match.group(3)
		link = '/static/upload/image-' + \
			article['old_id'] + str(i) + '.' + ext
		img = match.group(4)
		if img not in images:
			open('..' + link, 'wb').write(base64.b64decode(img))
			images.append(img)
		body = body.replace(match.group(2), link)
		print(link)
	article['body'] = body
	return article


def users(users_by_oid, users_by_slug, users_data):
	''' migrating users first '''
	# limiting
	limit = len(users_data)
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('migrating %d users...' % limit)
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
		id_map[user['old_id']] = user['id']
		counter += 1
	for entry in users_data:
		migrateUser_2stage(entry, id_map)
	try:
		open('migration/data/users.old_id.json', 'w').write(json.dumps(users_by_oid, cls=DateTimeEncoder))  # NOTE: by old_id
		open('migration/data/users.slug.json', 'w').write(json.dumps(users_by_slug, cls=DateTimeEncoder))  # NOTE: by slug
		print(str(len(users_by_slug.items())) + ' users migrated')
	except Exception:
		print('json dump error')
		print(users_by_oid)


def topics(export_topics, topics_by_slug, topics_by_cat, topics_by_tag, cats_data, tags_data):
	''' topics from categories and tags '''
	# limiting
	limit = len(cats_data) + len(tags_data)
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('migrating %d topics...' % limit)
	counter = 0
	for cat in cats_data:
		old_id = cat["createdBy"]
		# cat["createdBy"] = user_id_map[old_id]
		try: topic = migrateCategory(cat)
		except Exception as e: raise e
		topics_by_cat[topic['cat_id']] = topic
		topics_by_slug[topic['slug']] = topic
		counter += 1
	for tag in tags_data:
		old_id = tag["createdBy"]
		tag["createdBy"] = user_id_map.get(old_id, 0)
		topic = migrateTag(tag)
		topics_by_tag[topic['tag_id']] = topic
		if not topics_by_slug.get(topic['slug']): topics_by_slug[topic['slug']] = topic
		counter += 1
	export_topics = dict(topics_by_slug.items()) # sorted(topics_by_slug.items(), key=lambda item: str(item[1]['createdAt']))) # NOTE: sorting does not work :)
	open('migration/data/topics.slug.json','w').write(json.dumps(topics_by_slug,
														cls=DateTimeEncoder,
														indent=4,
														sort_keys=True,
														ensure_ascii=False))

	open('migration/data/topics.cat_id.json','w').write(json.dumps(topics_by_cat,
														cls=DateTimeEncoder,
														indent=4,
														sort_keys=True,
														ensure_ascii=False))

def shouts(content_data, shouts_by_slug, shouts_by_oid):
	''' migrating content items one by one '''
	# limiting
	limit = len(content_data)
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('migrating %d content items...' % limit)
	counter = 0
	discours_author = 0
	errored = []

	# limiting
	try: limit = int(sys.argv[2]) if len(sys.argv) > 2 else len(content_data)
	except ValueError:  limit = len(content_data)

	if not topics_by_cat:
		with local_session() as session:
			topics = session.query(Topic).all()
		print("loaded %s topics" % len(topics))
		for topic in topics:
			topics_by_cat[topic.cat_id] = topic

	for entry in content_data[:limit]:
		try:
			shout = migrateShout(entry, users_by_oid, topics_by_cat)
			author = shout['authors'][0]
			shout['authors'] = [ author.id, ]
			shouts_by_slug[shout['slug']] = shout
			shouts_by_oid[entry['_id']] = shout
			line = str(counter+1) + ': ' + shout['slug'] + " @" + str(author.slug)
			counter += 1
			if author.slug == 'discours': discours_author += 1
			print(line)
			# open('./shouts.id.log', 'a').write(line + '\n')
		except Exception as e:
			print(entry['_id'])
			errored.append(entry)
			raise e
	open('migration/data/shouts.old_id.json','w').write(json.dumps(shouts_by_oid, cls=DateTimeEncoder))
	open('migration/data/shouts.slug.json','w').write(json.dumps(shouts_by_slug, cls=DateTimeEncoder))
	print(str(counter) + '/' + str(len(content_data)) + ' content items were migrated')
	print(str(discours_author) + ' authored by @discours')
	
def export_shouts(shouts_by_slug, export_articles, export_authors, content_dict):
	# update what was just migrated or load json again
	if len(export_authors.keys()) == 0:
		export_authors = json.loads(open('../src/data/authors.json').read())
		print(str(len(export_authors.items())) + ' exported authors loaded')
	if len(export_articles.keys()) == 0:
		export_articles = json.loads(open('../src/data/articles.json').read())
		print(str(len(export_articles.items())) + ' exported articles loaded')
	
	# limiting
	limit = 33
	if len(sys.argv) > 2: limit = int(sys.argv[2])
	print('exporting %d articles to json...' % limit)
	
	# filter 
	export_list = [i for i in shouts_by_slug.items() if i[1]['layout'] == 'article']
	export_list = sorted(export_list, key=lambda item: item[1]['createdAt'] or OLD_DATE, reverse=True)
	print(str(len(export_list)) + ' filtered')
	export_list = export_list[:limit or len(export_list)]
	
	for (slug, article) in export_list:
		if article['layout'] == 'article':
			export_slug(slug, export_articles, export_authors, content_dict)
	
def export_body(article, content_dict):
	article = extract_images(article)
	metadata = get_metadata(article)
	content = frontmatter.dumps(frontmatter.Post(article['body'], **metadata))
	open('../content/discours.io/'+slug+'.md', 'w').write(content)
	open('../content/discours.io/'+slug+'.html', 'w').write(content_dict[article['old_id']]['body'])

def export_slug(slug, export_articles, export_authors, content_dict):
	print('exporting %s ' % slug)
	if export_authors == {}: 
		export_authors = json.loads(open('../src/data/authors.json').read())
		print(str(len(export_authors.items())) + ' exported authors loaded')
	if export_articles == {}:
		export_articles = json.loads(open('../src/data/articles.json').read())
		print(str(len(export_articles.items())) + ' exported articles loaded')
		
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
		comment = migrateComment(comment)
		id = comment.get('id')
		old_id = comment.get('old_id')
		id_map[old_id] = id
	for comment in comments_data:
		migrateComment_2stage(comment, id_map)
	print(str(len(id_map)) + ' comments exported')


def export_finish(export_articles = {}, export_authors = {}, export_topics = {}, export_comments = {}):
	open('../src/data/authors.json', 'w').write(json.dumps(export_authors,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print(str(len(export_authors.items())) + ' authors exported')
	open('../src/data/topics.json', 'w').write(json.dumps(export_topics,
														cls=DateTimeEncoder,
														indent=4,
														sort_keys=True,
														ensure_ascii=False))
	print(str(len(export_topics.keys())) + ' topics exported')
	
	open('../src/data/articles.json', 'w').write(json.dumps(export_articles,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print(str(len(export_articles.items())) + ' articles exported')
	open('../src/data/comments.json', 'w').write(json.dumps(export_comments,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print(str(len(export_comments.items())) + ' exported articles with comments')


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

				users_data = json.loads(open('migration/data/users.json').read())
				# users_dict = { x['_id']: x for x in users_data } # by id
				print(str(len(users_data)) + ' users loaded')
				users_by_oid = {}
				users_by_slug = {}

				user_id_map = {}
				with local_session() as session:
					users_list = session.query(User).all()
					for user in users_list:
						user_id_map[user.old_id] = user.id
						users_by_oid[user.old_id] = vars(user)

				tags_data = json.loads(open('migration/data/tags.json').read())
				print(str(len(tags_data)) + ' tags loaded')

				cats_data = json.loads(open('migration/data/content_item_categories.json').read())
				print(str(len(cats_data)) + ' cats loaded')
				topics_by_cat = {}
				topics_by_tag = {}
				topics_by_slug = {}

				content_data = json.loads(open('migration/data/content_items.json').read())
				content_dict = { x['_id']: x for x in content_data }
				print(str(len(content_data)) + ' content items loaded')
				shouts_by_slug = {}
				shouts_by_oid = {}

				comments_data = json.loads(open('migration/data/comments.json').read())
				print(str(len(comments_data)) + ' comments loaded')
				comments_by_post = {}
					# sort comments by old posts ids
				for old_comment in comments_data:
					cid = old_comment['contentItem']
					comments_by_post[cid] = comments_by_post.get(cid, [])
					if not old_comment.get('deletedAt', True):
						comments_by_post[cid].append(old_comment)
				print(str(len(comments_by_post.keys())) + ' articles with comments')

				export_articles = {} # slug: shout
				export_authors = {} # slug: user
				export_comments = {} # shout-slug: comment[] (list)
				export_topics = {} # slug: topic

				##################### COMMANDS ##########################3

				if cmd == "users":
					users(users_by_oid, users_by_slug, users_data)
				elif cmd == "topics":
					topics(export_topics, topics_by_slug, topics_by_cat, topics_by_tag, cats_data, tags_data)
				elif cmd == "shouts":
					shouts(content_data, shouts_by_slug, shouts_by_oid) # NOTE: listens limit
				elif cmd == "comments":
					comments(comments_data)
				elif cmd == "export_shouts":
					export_shouts(shouts_by_slug, export_articles, export_authors, content_dict)
				elif cmd == "all":
					users(users_by_oid, users_by_slug, users_data)
					topics(export_topics, topics_by_slug, topics_by_cat, topics_by_tag, cats_data, tags_data)
					shouts(content_data, shouts_by_slug, shouts_by_oid)
					comments(comments_data)
				elif cmd == 'slug':
					export_slug(sys.argv[2], export_articles, export_authors, content_dict)
				#export_finish(export_articles, export_authors, export_topics, export_comments)
	else:
		print('''
			usage: python migrate.py bson
			\n.. \ttopics <limit>
			\n.. \tusers <limit>
			\n.. \tshouts <limit>
			\n.. \texport_shouts <limit>
			\n.. \tslug <slug>
			\n.. \tall
			''')
