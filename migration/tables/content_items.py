from dateutil.parser import parse as date_parse
import frontmatter
import json
import sqlalchemy
from orm import Shout, ShoutTopic, ShoutRating, ShoutViewByDay, User, shout
# from bs4 import BeautifulSoup
from migration.html2text import html2text
from transliterate import translit
from datetime import datetime
from orm.base import local_session
from orm.community import Community
from migration.extract import extract
import os

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
	metadata['title'] = r.get('title', '').replace('{', '(').replace('}', ')')
	metadata['authors'] = r.get('authors')
	metadata['createdAt'] = r.get('createdAt', ts)
	metadata['layout'] = r['layout']
	metadata['topics'] = [topic['slug'] for topic in r['topics']]
	metadata['topics'].sort()
	if r.get('cover', False):
		metadata['cover'] = r.get('cover')
	return metadata


retopics = json.loads(open('migration/tables/replacements.json').read())

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

	# slug 

	s = entry.get('slug', '')
	fslugs = entry.get('friendlySlugs')
	if not s and fslugs:
		if type(fslugs) != 'list': fslugs = fslugs.get('slug', [])
		try: s = fslugs.pop(0).get('slug')
		except: raise Exception
	if s: r['slug'] = s
	else: raise Exception

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
	
	# cover

	if entry.get('image') is not None:
		r['cover'] = entry['image']['url']
	if entry.get('thumborId') is not None:
		r['cover'] = 'https://assets.discours.io/unsafe/1600x/' + entry['thumborId']
	if entry.get('updatedAt') is not None:
		r['updatedAt'] = date_parse(entry['updatedAt'])

	# body 

	body = ''
	body_orig = entry.get('body')
	if not body_orig: body_orig = ''

	# body modifications

	if entry.get('type') == 'Literature':
		for m in entry.get('media', []):
			t = m.get('title', '')
			if t: body_orig += '### ' + t + '\n'
			body_orig += (m.get('body', '') or '')
			body_orig += '\n' + m.get('literatureBody', '') + '\n'


	elif entry.get('type') == 'Video':
		providers = set([])
		video_url = ''
		require = False
		for m in entry.get('media', []):
			yt = m.get('youtubeId', '')
			vm = m.get('vimeoId', '')
			if yt:
				require = True
				providers.add('YouTube')
				video_url = 'https://www.youtube.com/watch?v=' + yt
				body += '<YouTube youtubeId=\'' + yt + '\' />\n'
			if vm:
				require = True
				providers.add('Vimeo')
				video_url = 'https://vimeo.com/' + vm
				body += '<Vimeo vimeoId=\''  + vm + '\' />\n'
			body += extract(html2text(m.get('body', '')), entry['_id'])
			if video_url == '#': print(entry.get('media', 'UNKNOWN MEDIA PROVIDER!'))
		if require: body = 'import { ' + ','.join(list(providers)) + ' } from \'solid-social\'\n\n' + body + '\n'
		body += extract(html2text(body_orig), entry['_id'])

	elif entry.get('type') == 'Music':
		require = False
		for m in entry.get('media', []):
			if 'fileUrl' in m:
				require = True
				artist = m.get('performer')
				trackname = ''
				if artist: trackname += artist + ' - '
				trackname += m.get('title','')
				body += '<MusicPlayer src=\"' + m['fileUrl'] + '\" title=\"' + trackname + '\" />\n' 
				body += extract(html2text(m.get('body', '')), entry['_id'])
			else:
				print(m)
		if require: body = 'import MusicPlayer from \'$/components/Article/MusicPlayer\'\n\n' + body + '\n'
		body += extract(html2text(body_orig), entry['_id'])

	elif entry.get('type') == 'Image':
		cover = r.get('cover')
		images = {}
		for m in entry.get('media', []):
			t = m.get('title', '')
			if t: body += '#### ' + t + '\n'
			u = m.get('image', {}).get('url', '')
			if 'cloudinary' in u:
				u = m.get('thumborId')
				if not u: u = cover
			if u not in images.keys():
				if u.startswith('production'): u = 'https://discours-io.s3.amazonaws.com/' + u 
				body += '![' + m.get('title','').replace('\n', ' ') + '](' + u + ')\n' # TODO: gallery here
				images[u] = u
			body += extract(html2text(m.get('body', '')), entry['_id']) + '\n'
		body += extract(html2text(body_orig), entry['_id'])

	# simple post or no body stored
	if body == '': 
		if not body_orig:
			print('[migration] using body history...')
			try: body_orig += entry.get('bodyHistory', [{'body': ''}])[0].get('body', '')
			except: pass
		# need to extract
		# body_html = str(BeautifulSoup(body_orig, features="html.parser"))
		body += extract(html2text(body_orig), entry['_id'])
	else:
		# EVERYTHING IS FINE HERE
		pass
	
	# replace some topics
	for oldtopicslug, newtopicslug in retopics.items():
		body.replace(oldtopicslug, newtopicslug)

	# authors

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
	r['body'] = body
	shout_dict = r.copy()
	author = { # a short version for public listings
		'slug': userdata.get('slug', 'discours'),
		'name': userdata.get('name', 'Дискурс'),
		'userpic': userdata.get('userpic', '')
	}
	shout_dict['authors'] = [ author, ]

	# save mdx for prerender if published

	if entry['published']:
		metadata = get_metadata(shout_dict)
		content = frontmatter.dumps(frontmatter.Post(r['body'], **metadata))
		ext = 'mdx'
		parentDir = '/'.join(os.getcwd().split('/')[:-1])
		filepath =  parentDir + '/discoursio-web/content/' + r['slug']
		# print(filepath)
		bc = bytes(content,'utf-8').decode('utf-8','ignore')
		open(filepath + '.' + ext, 'w').write(bc)
		# open(filepath + '.html', 'w').write(body_orig)

	# save shout to db

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
				print('[migration] content_items error: \n%r' % entry)
		assert user, 'could not get a user'
		shout_dict['authors'] = [ user, ] 
		
		# create shout

		s = object()
		try: s = Shout.create(**shout_dict)
		except: print('[migration] content_items error: \n%r' % entry)
		
		# shout ratings
		
		shout_dict['ratings'] = []
		for shout_rating_old in entry.get('ratings',[]):
			with local_session() as session:
				rater = session.query(User).\
					filter(User.old_id == shout_rating_old['createdBy']).first()
			if rater:
				shout_rating_dict = {
					'value': shout_rating_old['value'],
					'rater': rater.slug,
					'shout': s.slug
				}
				cts = shout_rating_old.get('createdAt')
				if cts: shout_rating_dict['ts'] = date_parse(cts)
				try: 
					shout_rating = session.query(ShoutRating).\
						filter(ShoutRating.shout == s.slug).\
						filter(ShoutRating.rater == rater.slug).first()
					if shout_rating:
						shout_rating_dict['value'] += int(shout_rating.value or 0)
						shout_rating.update(shout_rating_dict)
					else: ShoutRating.create(**shout_rating_dict)
					shout_dict['ratings'].append(shout_rating_dict)
				except sqlalchemy.exc.IntegrityError: 
					print('[migration] shout_rating error: \n%r' % shout_rating_dict)
					pass

		# shout topics

		shout_dict['topics'] = []
		for topic in r['topics']:
			try:
				tpc = topics_by_oid[topic['oid']]
				slug = retopics.get(tpc['slug'], tpc['slug'])
				ShoutTopic.create(**{ 'shout': s.slug, 'topic': slug })
				shout_dict['topics'].append(slug)
			except sqlalchemy.exc.IntegrityError:
				pass

		# shout views

		views = entry.get('views', 1)
		ShoutViewByDay.create(
			shout = s.slug,
			value = views
		)

	except Exception as e: 
		raise e
	shout_dict['old_id'] = entry.get('_id')
	return shout_dict, topic_errors
