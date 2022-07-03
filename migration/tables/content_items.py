from dateutil.parser import parse as date_parse
import frontmatter
import json
from orm import Shout, ShoutTopic, ShoutRating, ShoutViewByDay, User, shout
from transliterate import translit
from datetime import datetime
from orm.base import local_session
from orm.community import Community
from migration.extract import prepare_body
import os

DISCOURS_USER = {
	'id': 9999999,
	'slug': 'discours',
	'name': 'Дискурс',
	'userpic': 'https://discours.io/images/logo-mini.svg',
	'createdAt': '2016-03-05 22:22:00.350000'
}
OLD_DATE = '2016-03-05 22:22:00.350000'
retopics = json.loads(open('migration/tables/replacements.json').read())
ts = datetime.now()
type2layout = {
	'Article': 'article',
	'Literature': 'prose',
	'Music': 'music',
	'Video': 'video',
	'Image': 'image'
}

def get_metadata(r):
	metadata = {}
	metadata['title'] = r.get('title', '').replace('{', '(').replace('}', ')')
	metadata['authors'] = r.get('authors')
	metadata['createdAt'] = r.get('createdAt', ts)
	metadata['layout'] = r['layout']
	metadata['topics'] = [topic['slug'] for topic in r['topics']]
	metadata['topics'].sort()
	if r.get('cover', False):
		metadata['cover'] = r.get('cover')
	return metadata

def migrate(entry, users_by_oid, topics_by_oid):
	# init, set title and layout
	r = {
		'layout': type2layout[entry['type']],
		'title': entry['title'],
		'community': Community.default_community.id,
		'authors': [],
		'topics': [],
		'rating': 0,
		'ratings': [],
		'createdAt': []
	}

	# slug 

	s = entry.get('slug', '')
	fslugs = entry.get('friendlySlugs')
	if not s and fslugs:
		if type(fslugs) != 'list': fslugs = fslugs.get('slug', [])
		try: s = fslugs.pop(0).get('slug')
		except: raise Exception
	if s: r['slug'] = s
	else: raise Exception
	
	# cover
	c = ''
	if entry.get('thumborId'):
		c = 'https://assets.discours.io/unsafe/1600x/' + entry['thumborId']
	else:
		c = entry.get('image', {}).get('url')
		if not c or 'cloudinary' in c:
			c = ''
	r['cover'] = c

	# timestamps

	r['createdAt'] = date_parse(entry.get('createdAt', OLD_DATE))
	r['updatedAt'] = date_parse(entry['updatedAt']) if 'updatedAt' in entry else ts
	if entry.get('published'): 
		r['publishedAt'] = date_parse(entry.get('publishedAt', OLD_DATE))
		if r['publishedAt'] == OLD_DATE: r['publishedAt'] = ts
	if 'deletedAt' in entry: r['deletedAt'] = date_parse(entry['deletedAt'])

	# connected users' data

	# r['deletedBy'] = entry.get('deletedBy', '0') # TypeError: 'deletedBy' is an invalid keyword argument for Shout

	oid = entry.get('createdBy', '') 
	userdata = users_by_oid.get(oid, {})
	if not userdata.get('slug'):
		app = entry.get('application')
		if app:
			userslug = translit(app['name'], 'ru', reversed=True).replace(' ', '-').replace('\'', '').replace('.', '-').lower()
			userdata = {
				'username': app['email'],
				'email': app['email'],
				'name': app['name'],
				'bio': app.get('bio', ''),
				'emailConfirmed': False,
				'slug': userslug,
				'createdAt': ts,
				'wasOnlineAt': ts
			}
	if userdata == {}: 
		userdata = {
			'name': 'Дискурс',
			'slug': 'discours',
			'userpic': 'https://discours.io/image/logo-mini.svg'
		} 

	author = { # a short version for public listings
		'slug': userdata.get('slug', 'discours'),
		'name': userdata.get('name', 'Дискурс'),
		'userpic': userdata.get('userpic', '')
	}
	r['authors'] = [ author, ]
	# body 

	body = prepare_body(entry)

	# save mdx for prerender if published

	r['body'] = body
	if entry.get('published'):
		content = ''
		metadata = get_metadata(r)
		content = frontmatter.dumps(frontmatter.Post(r['body'], **metadata))
		ext = 'mdx'
		parentDir = '/'.join(os.getcwd().split('/')[:-1])
		filepath =  parentDir + '/discoursio-web/content/' + r['slug']
		# print(filepath)
		bc = bytes(content,'utf-8').decode('utf-8','ignore')
		open(filepath + '.' + ext, 'w').write(bc)
		# open(filepath + '.html', 'w').write(body_orig)


	# topics

	category = entry['category']
	mainTopic = topics_by_oid.get(category)
	if mainTopic:
		r['mainTopic'] = mainTopic["slug"]
	topic_oids = [category, ]
	topic_errors = []
	topic_oids.extend(entry.get('tags', []))
	for oid in topic_oids:
		if oid in topics_by_oid:
			r['topics'].append(topics_by_oid[oid])
		else:
			# print('ERROR: unknown old topic id: ' + oid)
			topic_errors.append(oid)

	# set prepared shout data
	
	shout_dict = r.copy() 
	del shout_dict['topics'] # FIXME: AttributeError: 'str' object has no attribute '_sa_instance_state'
	del shout_dict['rating'] # FIXME: TypeError: 'rating' is an invalid keyword argument for Shout
	del shout_dict['ratings']

	# get author

	user = None
	email = userdata.get('email')
	authorslug = userdata.get('slug')
	with local_session() as session:
		try:
			if email: user = session.query(User).filter(User.email == email).first()
			if not user and authorslug: user = session.query(User).filter(User.slug == authorslug).first()
			if not user and userdata: user = User.create(**userdata)
		except:
			print('[migration] shout author error: \n%r' % entry)
			raise Exception
	assert user, 'could not get a user'
	shout_dict['authors'] = [ user, ] 

	# save shout to db

	s = object()
	try: s = Shout.create(**shout_dict)
	except: print('[migration] shout create error: \n%r' % shout_dict)

	
	# shout ratings
	try:
		shout_dict['ratings'] = []
		for shout_rating_old in entry.get('ratings',[]):
			with local_session() as session:
				rater = session.query(User).filter(User.old_id == shout_rating_old['createdBy']).first()
				if rater:
					shout_rating_dict = {
						'value': shout_rating_old['value'],
						'rater': rater.slug,
						'shout': s.slug
					}
					cts = shout_rating_old.get('createdAt')
					if cts: shout_rating_dict['ts'] = date_parse(cts)
					shout_rating = session.query(ShoutRating).\
						filter(ShoutRating.shout == s.slug).\
						filter(ShoutRating.rater == rater.slug).first()
					if shout_rating:
						shout_rating_dict['value'] = int(shout_rating_dict['value'] or 0) + int(shout_rating.value or 0)
						shout_rating.update(shout_rating_dict)
					else: ShoutRating.create(**shout_rating_dict)
					shout_dict['ratings'].append(shout_rating_dict)
	except:
		print('[migration] shout rating error: \n%r' % shout_rating_old)
		# raise Exception

	# shout topics
	try:
		shout_dict['topics'] = []
		for topic in r['topics']:
			tpc = topics_by_oid[topic['oid']]
			oldslug = tpc['slug']
			newslug = retopics.get(oldslug, oldslug)
			need_create_topic = False
			if newslug:
				with local_session() as session:
					shout_topic_new = session.query(ShoutTopic)\
						.filter(ShoutTopic.shout == s.slug)\
						.filter(ShoutTopic.topic == newslug).first()
					shout_topic_old = session.query(ShoutTopic)\
						.filter(ShoutTopic.shout == s.slug)\
						.filter(ShoutTopic.topic == oldslug).first()
					if not shout_topic_new:
						if shout_topic_old:
							shout_topic_old.update({ 'slug': newslug })
						else: 
							need_create_topic = True
				if need_create_topic:
					ShoutTopic.create(**{ 'shout': s.slug, 'topic': newslug })
			shout_dict['topics'].append(newslug)
	except:
		print('[migration] shout topic error: \n%r' % entry)
		raise Exception

	# shout views
	try:
		views = entry.get('views', 1)
		ShoutViewByDay.create(
			shout = s.slug,
			value = views
		)
	except:
		print('[migration] shout view error: \n%r' % entry)
		# raise Exception
	shout_dict['old_id'] = entry.get('_id')
	return shout_dict, topic_errors
