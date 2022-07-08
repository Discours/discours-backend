
from datetime import datetime
import json
import os
import frontmatter
from migration.extract import extract_html, prepare_body
from migration.tables.users import migrate_email_subscription
from migration.utils import DateTimeEncoder

OLD_DATE = '2016-03-05 22:22:00.350000'
EXPORT_DEST = '../discoursio-web/data/'
parentDir = '/'.join(os.getcwd().split('/')[:-1])
contentDir = parentDir + '/discoursio-web/content/'
ts = datetime.now()

def get_metadata(r):
	authors = []
	for a in r['authors']:
		authors.append({ # a short version for public listings
			'slug': a.slug or 'discours',
			'name': a.name or 'Дискурс',
			'userpic': a.userpic or 'https://discours.io/static/img/discours.png'
		})
	metadata = {}
	metadata['title'] = r.get('title', '').replace('{', '(').replace('}', ')')
	metadata['authors'] = authors
	metadata['createdAt'] = r.get('createdAt', ts)
	metadata['layout'] = r['layout']
	metadata['topics'] = [topic for topic in r['topics']]
	metadata['topics'].sort()
	if r.get('cover', False): metadata['cover'] = r.get('cover')
	return metadata
	
def export_mdx(r):
	# print('[export] mdx %s' % r['slug']) 
	content = ''
	metadata = get_metadata(r)
	content = frontmatter.dumps(frontmatter.Post(r['body'], **metadata))
	ext = 'mdx'
	filepath = contentDir + r['slug']
	bc = bytes(content,'utf-8').decode('utf-8','ignore')
	open(filepath + '.' + ext, 'w').write(bc)

def export_body(shout, storage):
	entry = storage['content_items']['by_oid'][shout['oid']]
	if entry:
		shout['body'] = prepare_body(entry)
		export_mdx(shout)
		print('[export] html for %s' % shout['slug'])
		body = extract_html(entry)
		open(contentDir + shout['slug'] + '.html', 'w').write(body)
	else:
		raise Exception('no content_items entry found')

def export_slug(slug, storage):
	shout = storage['shouts']['by_slug'][slug]
	shout = storage['shouts']['by_slug'].get(slug)
	assert shout, '[export] no shout found by slug: %s ' % slug
	author = shout['authors'][0]
	assert author, '[export] no author error'
	export_body(shout, storage)

def export_email_subscriptions():
	email_subscriptions_data = json.loads(open('migration/data/email_subscriptions.json').read())
	for data in email_subscriptions_data:
		migrate_email_subscription(data)
	print('[migration] ' + str(len(email_subscriptions_data)) + ' email subscriptions exported')

def export_shouts(storage):
	# update what was just migrated or load json again
	if len(storage['users']['by_slugs'].keys()) == 0:
		storage['users']['by_slugs'] = json.loads(open(EXPORT_DEST + 'authors.json').read())
		print('[migration] ' + str(len(storage['users']['by_slugs'].keys())) + ' exported authors loaded')
	if len(storage['shouts']['by_slugs'].keys()) == 0:
		storage['shouts']['by_slugs'] = json.loads(open(EXPORT_DEST + 'articles.json').read())
		print('[migration] ' + str(len(storage['shouts']['by_slugs'].keys())) + ' exported articles loaded')
	for slug in storage['shouts']['by_slugs'].keys(): export_slug(slug, storage)

def export_json(export_articles = {}, export_authors = {}, export_topics = {}, export_comments = {}):
	open(EXPORT_DEST + 'authors.json', 'w').write(json.dumps(export_authors,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print('[migration] ' + str(len(export_authors.items())) + ' authors exported')
	open(EXPORT_DEST + 'topics.json', 'w').write(json.dumps(export_topics,
														cls=DateTimeEncoder,
														indent=4,
														sort_keys=True,
														ensure_ascii=False))
	print('[migration] ' + str(len(export_topics.keys())) + ' topics exported')
	
	open(EXPORT_DEST + 'articles.json', 'w').write(json.dumps(export_articles,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print('[migration] ' + str(len(export_articles.items())) + ' articles exported')
	open(EXPORT_DEST + 'comments.json', 'w').write(json.dumps(export_comments,
															cls=DateTimeEncoder,
															indent=4,
															sort_keys=True,
															ensure_ascii=False))
	print('[migration] ' + str(len(export_comments.items())) + ' exported articles with comments')

