from dateutil.parser import parse as date_parse
import frontmatter
import json
import sqlite3
import sqlalchemy
from orm import Shout, Comment, Topic, ShoutTopic, ShoutRating, ShoutViewByDay, User
from bs4 import BeautifulSoup
from migration.html2text import html2text
from migration.tables.comments import migrate as migrateComment
from transliterate import translit
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from orm.base import local_session
from orm.community import Community
	
DISCOURS_USER = {
	'id': 9999999,
	'slug': 'discours',
	'name': 'Дискурс',
	'userpic': 'https://discours.io/images/logo-mini.svg',
	'createdAt': '2016-03-05 22:22:00.350000'
}

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
	metadata['title'] = r.get('title')
	metadata['authors'] = r.get('authors')
	metadata['createdAt'] = r.get('createdAt', ts)
	metadata['layout'] = r['layout']
	metadata['topics'] = [topic['slug'] for topic in r['topics']]
	if r.get('cover', False):
		metadata['cover'] = r.get('cover')
	return metadata

def migrate(entry, users_by_oid, topics_by_oid):
	'''
	type Shout {
		slug: String!
		author: Int!
		body: String!
		createdAt: DateTime!
		updatedAt: DateTime!
		deletedAt: DateTime
		deletedBy: Int
		rating: Int
		ratings: [Rating]
		published: Bool!
		publishedAt: DateTime # if there is no published field - it is not published
		replyTo: String # another shout
		tags: [String] # actual values
		topics: [String] # topic-slugs, order has matter
		title: String
		versionOf: String
		visibleForRoles: [String] # role ids are strings
		visibleForUsers: [Int]
		views: Int
	}
	'''
	# print(entry)
	content = ''
	r = {
		'layout': type2layout[entry['type']],
		'title': entry['title'],
		'community': Community.default_community.id,
		'authors': [],
		'topics': [],
		'rating': entry.get('rating', 0),
		'ratings': [],
		'createdAt': entry.get('createdAt', '2016-03-05 22:22:00.350000')
	}
	r['slug'] = entry.get('slug', '')
	body_orig = entry.get('body', '')
	if not r['slug'] and entry.get('friendlySlugs') is not None:
		r['slug'] = entry['friendlySlugs']['slug'][0]['slug']
		if(r['slug'] is None):
			r['slug'] = entry['friendlySlugs'][0]['slug']
	if not r['slug']:
		print('NO SLUG ERROR')
		# print(entry)
		raise Exception

	category = entry['category']
	mainTopic = topics_by_oid.get(category)
	if mainTopic:
		r['mainTopic'] = mainTopic["slug"]
	topic_oids = set([category])
	topic_oids.update(entry.get("tags", []))
	for oid in topic_oids:
		if oid in topics_by_oid:
			r['topics'].append(topics_by_oid[oid])

	if entry.get('image') is not None:
		r['cover'] = entry['image']['url']
	if entry.get('thumborId') is not None:
		r['cover'] = 'https://assets.discours.io/unsafe/1600x/' + entry['thumborId']
	if entry.get('updatedAt') is not None:
		r['updatedAt'] = date_parse(entry['updatedAt'])
	if entry.get('type') == 'Literature':
		media = entry.get('media', '')
		# print(media[0]['literatureBody'])
		if type(media) == list:
			body_orig = media[0].get('literatureBody', '')
			if body_orig == '':
				print('EMPTY BODY!')
			else:
				body_html = str(BeautifulSoup(
					body_orig, features="html.parser"))
				r['body'] = body_html # html2text(body_html)
		else:
			print(r['slug'] + ': literature has no media')
	elif entry.get('type') == 'Video':
		m = entry['media'][0]
		yt = m.get('youtubeId', '')
		vm = m.get('vimeoId', '')
		video_url = 'https://www.youtube.com/watch?v=' + yt if yt else '#'
		if video_url == '#':
			video_url = 'https://vimeo.com/' + vm if vm else '#'
		if video_url == '#':
			print(entry.get('media', 'NO MEDIA!'))
			# raise Exception
		r['body'] = '<ShoutVideo src=\"' + video_url + \
			'\" />' + html2text(m.get('body', ''))  # FIXME
	elif entry.get('type') == 'Music':
		r['body'] = '<ShoutMusic media={\"' + \
			json.dumps(entry['media']) + '\"} />'  # FIXME
	if r.get('body') is None:
		body_orig = entry.get('body', '')
		body_html = str(BeautifulSoup(body_orig, features="html.parser"))
		r['body'] = body_html # html2text(body_html)
	body = r.get('body', '')
	
	# get author data
	userdata = {}
	try: userdata = users_by_oid[entry['createdBy']]
	except KeyError:
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

	# set author data
	shout_dict = r.copy()
	author = { # a short version for public listings
		'slug': userdata.get('slug', 'discours'),
		'name': userdata.get('name', 'Дискурс'),
		'userpic': userdata.get('userpic', '')
	}
	shout_dict['authors'] = [ author, ]
	
	if entry['published']:
		metadata = get_metadata(r)
		content = frontmatter.dumps(frontmatter.Post(body, **metadata))
		ext = 'md'
		open('migration/content/' + r['layout'] + '/' + r['slug'] + '.' + ext, 'w').write(content)
	try:
		shout_dict['createdAt'] = date_parse(r.get('createdAt')) if entry.get('createdAt') else ts
		shout_dict['publishedAt'] = date_parse(entry.get('publishedAt')) if entry.get('published') else None

		if entry.get('deletedAt') is not None:
			shout_dict['deletedAt'] = date_parse(entry.get('deletedAt'))
			shout_dict['deletedBy'] = entry.get('deletedBy', '0')
		
		del shout_dict['topics'] # FIXME: AttributeError: 'str' object has no attribute '_sa_instance_state'
		del shout_dict['rating'] # FIXME: TypeError: 'rating' is an invalid keyword argument for Shout
		del shout_dict['ratings']
		
		# get user
		
		user = None
		email = userdata.get('email')
		slug = userdata.get('slug')
		with local_session() as session:
			try:
				if email: user = session.query(User).filter(User.email == email).first()
				if not user and slug: user = session.query(User).filter(User.slug == slug).first()
				if not user and userdata: user = User.create(**userdata)
			except:
				print(userdata)
		assert user, 'could not get a user'
		
		shout_dict['authors'] = [ user, ] 
		try:
			s = Shout.create(**shout_dict)

			# shout ratings
			shout_dict['ratings'] = []
			for shout_rating_old in entry.get('ratings',[]):
				with local_session() as session:
					rater = session.query(User).\
						filter(User.old_id == shout_rating_old['createdBy']).first()
				if rater:
					shout_rating_dict = {
						'value': shout_rating_old['value'],
						'rater': rater.id,
						'shout': s.slug
					}
					cts = shout_rating_old.get('createdAt')
					if cts: shout_rating_dict['rater_id'] = date_parse(cts)
					try: shout_rating = ShoutRating.create(**shout_rating_dict)
					except sqlalchemy.exc.IntegrityError: pass
					shout_dict['ratings'].append(shout_rating_dict)

			# shout topics
			shout_dict['topics'] = []
			for topic in r['topics']:
				try:
					ShoutTopic.create(**{ 'shout': s.slug, 'topic': topic['slug'] })
					shout_dict['topics'].append(topic['slug'])
				except sqlalchemy.exc.IntegrityError:
					pass

			views = entry.get('views', 1)
			ShoutViewByDay.create(
				shout = s.slug,
				value = views
			)

		except Exception as e: 
			raise e
	except Exception as e:
		if not shout_dict['body']: r['body'] = 'body moved'
		raise e
	shout_dict['old_id'] = entry.get('_id')
	return shout_dict # for json
