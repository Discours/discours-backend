from dateutil.parser import parse as date_parse
import sqlalchemy
from orm.shout import Shout, ShoutTopic, User
from storages.viewed import ViewedByDay
from transliterate import translit
from datetime import datetime
from orm.base import local_session
from migration.extract import prepare_html_body
from orm.community import Community
from orm.reaction import Reaction, ReactionKind

OLD_DATE = '2016-03-05 22:22:00.350000'
ts = datetime.now()
type2layout = {
	'Article': 'article',
	'Literature': 'prose',
	'Music': 'music',
	'Video': 'video',
	'Image': 'image'
}

def get_shout_slug(entry):
	slug = entry.get('slug', '')
	if not slug:
		for friend in entry.get('friendlySlugs', []):
			slug = friend.get('slug', '')
			if slug: break
	return slug

def migrate(entry, storage):
	# init, set title and layout
	r = {
		'layout': type2layout[entry['type']],
		'title': entry['title'],
		'community': Community.default_community.id,
		'authors': [],
		'topics': set([]),
		# 'rating': 0,
		# 'ratings': [],
		'createdAt': []
	}
	topics_by_oid = storage['topics']['by_oid']
	users_by_oid = storage['users']['by_oid']

	# author

	oid = entry.get('createdBy', entry.get('_id', entry.get('oid'))) 
	userdata = users_by_oid.get(oid)
	if not userdata:
		app = entry.get('application')
		if app:
			userslug = translit(app['name'], 'ru', reversed=True)\
				.replace(' ', '-')\
				.replace('\'', '')\
				.replace('.', '-').lower()
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
		else: 
			userdata = User.default_user.dict()
	assert userdata, 'no user found for %s from ' % [oid, len(users_by_oid.keys())]
	r['authors'] = [userdata, ]

	# slug 

	slug = get_shout_slug(entry)
	if slug: r['slug'] = slug
	else: raise Exception
	
	# cover
	c = ''
	if entry.get('thumborId'):
		c = 'https://assets.discours.io/unsafe/1600x/' + entry['thumborId']
	else:
		c = entry.get('image', {}).get('url')
		if not c or 'cloudinary' in c: c = ''
	r['cover'] = c

	# timestamps

	r['createdAt'] = date_parse(entry.get('createdAt', OLD_DATE))
	r['updatedAt'] = date_parse(entry['updatedAt']) if 'updatedAt' in entry else ts
	if entry.get('published'): 
		r['publishedAt'] = date_parse(entry.get('publishedAt', OLD_DATE))
		if r['publishedAt'] == OLD_DATE: r['publishedAt'] = ts
	if 'deletedAt' in entry: r['deletedAt'] = date_parse(entry['deletedAt'])

	# topics
	category = entry['category']
	mainTopic = topics_by_oid.get(category)
	if mainTopic:
		r['mainTopic'] = storage['replacements'].get(mainTopic["slug"], mainTopic["slug"])
	topic_oids = [category, ]
	topic_oids.extend(entry.get('tags', []))
	for oid in topic_oids:
		if oid in storage['topics']['by_oid']:
			r['topics'].add(storage['topics']['by_oid'][oid]['slug'])
		else:
			print('[migration] unknown old topic id: ' + oid)
	r['topics'] = list(r['topics'])
	
	entry['topics'] = r['topics']
	entry['cover'] = r['cover']
	entry['authors'] = r['authors']

	# body 
	r['body'] = prepare_html_body(entry)

	# save shout to db

	s = object()
	shout_dict = r.copy() 
	user = None
	del shout_dict['topics'] # FIXME: AttributeError: 'str' object has no attribute '_sa_instance_state'
	#del shout_dict['rating'] # FIXME: TypeError: 'rating' is an invalid keyword argument for Shout
	#del shout_dict['ratings']
	email = userdata.get('email')
	slug = userdata.get('slug')
	with local_session() as session:
		# c = session.query(Community).all().pop()
		if email: user = session.query(User).filter(User.email == email).first()
		if not user and slug: user = session.query(User).filter(User.slug == slug).first()
		if not user and userdata: 
			try: user = User.create(**userdata)
			except sqlalchemy.exc.IntegrityError:
				print('[migration] user error: ' + userdata)
			userdata['id'] = user.id
			userdata['createdAt'] = user.createdAt
			storage['users']['by_slug'][userdata['slug']] = userdata
			storage['users']['by_oid'][entry['_id']] = userdata
	assert user, 'could not get a user'
	shout_dict['authors'] = [ user, ] 

	try: 
		s = Shout.create(**shout_dict)
	except sqlalchemy.exc.IntegrityError as e:
		with local_session() as session:
			s = session.query(Shout).filter(Shout.slug == shout_dict['slug']).first()
			bump = False
			if s: 
				for key in shout_dict:
					if key in s.__dict__:
						if s.__dict__[key] != shout_dict[key]:
							print('[migration] shout already exists, but differs in %s' % key)
							bump = True
					else:
						print('[migration] shout already exists, but lacks %s' % key)
						bump = True
				if bump:
					s.update(shout_dict)
			else:
				print('[migration] something went wrong with shout: \n%r' % shout_dict)
				raise e
			session.commit()
	except:
		print(s)
		raise Exception
	

	# shout topics aftermath
	shout_dict['topics'] = []
	for tpc in r['topics']:
		oldslug = tpc
		newslug = storage['replacements'].get(oldslug, oldslug)
		if newslug:
			with local_session() as session:
				shout_topic_old = session.query(ShoutTopic)\
					.filter(ShoutTopic.shout == shout_dict['slug'])\
					.filter(ShoutTopic.topic == oldslug).first()
				if shout_topic_old: 
					shout_topic_old.update({ 'slug': newslug })
				else: 
					shout_topic_new = session.query(ShoutTopic)\
						.filter(ShoutTopic.shout == shout_dict['slug'])\
						.filter(ShoutTopic.topic == newslug).first()
					if not shout_topic_new: 
						try: ShoutTopic.create(**{ 'shout': shout_dict['slug'], 'topic': newslug })
						except: print('[migration] shout topic error: ' + newslug)
				session.commit()
			if newslug not in shout_dict['topics']:
				shout_dict['topics'].append(newslug)
		else:
			print('[migration] ignored topic slug: \n%r' % tpc['slug'])
			# raise Exception

	# content_item ratings to reactions
	try:
		for content_rating in entry.get('ratings',[]):
			with local_session() as session:
				rater = session.query(User).filter(User.oid == content_rating['createdBy']).first()
				reactedBy = rater if rater else session.query(User).filter(User.slug == 'noname').first()
				if rater:
					reaction_dict = {
						'kind': ReactionKind.LIKE if content_rating['value'] > 0 else ReactionKind.DISLIKE,
						'createdBy': reactedBy.slug,
						'shout': shout_dict['slug']
					}
					cts = content_rating.get('createdAt')
					if cts: reaction_dict['createdAt'] = date_parse(cts)
					reaction = session.query(Reaction).\
						filter(Reaction.shout == reaction_dict['shout']).\
						filter(Reaction.createdBy == reaction_dict['createdBy']).\
						filter(Reaction.kind == reaction_dict['kind']).first()
					if reaction:
						reaction_dict['kind'] = ReactionKind.AGREE if content_rating['value'] > 0 else ReactionKind.DISAGREE,
						reaction.update(reaction_dict)
					else: Reaction.create(**reaction_dict)
					# shout_dict['ratings'].append(reaction_dict)
	except:
		print('[migration] content_item.ratings error: \n%r' % content_rating)
		raise Exception

	# shout views
	ViewedByDay.create( shout = shout_dict['slug'], value = entry.get('views', 1) )
	# del shout_dict['ratings']
	shout_dict['oid'] = entry.get('_id')
	storage['shouts']['by_oid'][entry['_id']] = shout_dict
	storage['shouts']['by_slug'][slug] = shout_dict
	return shout_dict
