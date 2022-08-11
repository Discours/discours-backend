import sqlalchemy
from migration.html2text import html2text
from orm import User, UserRating
from dateutil.parser import parse
from base.orm import local_session

def migrate(entry):
	if 'subscribedTo' in entry: del entry['subscribedTo']
	email = entry['emails'][0]['address']
	user_dict = {
		'oid': entry['_id'],
		'roles': [],
		'ratings': [],
		'username': email,
		'email': email,
		'password': entry['services']['password'].get('bcrypt', ''),
		'createdAt': parse(entry['createdAt']),
		'emailConfirmed': bool(entry['emails'][0]['verified']),
		'muted': False, # amnesty
		'bio': entry['profile'].get('bio', ''),
		'notifications': [],
		'createdAt': parse(entry['createdAt']),
		'roles': [], # entry['roles'] # roles by community
		'ratings': [], # entry['ratings']
		'links': [],
		'name': 'anonymous'
	}
	if 'updatedAt' in entry: user_dict['updatedAt'] = parse(entry['updatedAt'])
	if 'wasOnineAt' in entry: user_dict['wasOnlineAt'] = parse(entry['wasOnlineAt'])
	if entry.get('profile'):
		# slug
		user_dict['slug'] = entry['profile'].get('path')
		user_dict['bio'] = html2text(entry.get('profile').get('bio') or '')

		# userpic
		try: user_dict['userpic'] = 'https://assets.discours.io/unsafe/100x/' + entry['profile']['thumborId']
		except KeyError:
			try: user_dict['userpic'] = entry['profile']['image']['url']
			except KeyError: user_dict['userpic'] = ''

		# name
		fn = entry['profile'].get('firstName', '')
		ln = entry['profile'].get('lastName', '')
		name = user_dict['slug'] if user_dict['slug'] else 'noname'
		name = fn if fn else name
		name = (name + ' ' + ln) if ln else name
		name = entry['profile']['path'].lower().replace(' ', '-') if len(name) < 2 else name
		user_dict['name'] = name

		# links
		fb = entry['profile'].get('facebook', False)
		if fb: user_dict['links'].append(fb)
		vk = entry['profile'].get('vkontakte', False)
		if vk: user_dict['links'].append(vk)
		tr = entry['profile'].get('twitter', False)
		if tr: user_dict['links'].append(tr)
		ws = entry['profile'].get('website', False)
		if ws: user_dict['links'].append(ws)

	# some checks
	if not user_dict['slug'] and len(user_dict['links']) > 0: 
		user_dict['slug'] = user_dict['links'][0].split('/')[-1]

	user_dict['slug'] = user_dict.get('slug', user_dict['email'].split('@')[0])
	oid = user_dict['oid']
	try: user = User.create(**user_dict.copy())
	except sqlalchemy.exc.IntegrityError:
		print('[migration] cannot create user ' + user_dict['slug'])
		with local_session() as session:
			old_user = session.query(User).filter(User.slug == user_dict['slug']).first()
			old_user.oid = oid
			user = old_user
			if not user:
				print('[migration] ERROR: cannot find user ' + user_dict['slug'])
				raise Exception
	user_dict['id'] = user.id
	return user_dict

def migrate_2stage(entry, id_map):
	ce = 0
	for rating_entry in entry.get('ratings',[]):
		rater_oid = rating_entry['createdBy']
		rater_slug = id_map.get(rater_oid)
		if not rater_slug:
			ce +=1
			# print(rating_entry)
			continue
		oid = entry['_id']
		author_slug = id_map.get(oid)
		user_rating_dict = {
			'value': rating_entry['value'],
			'rater': rater_slug,
			'user': author_slug
		}
		with local_session() as session:
			try:
				user_rating = UserRating.create(**user_rating_dict)
			except sqlalchemy.exc.IntegrityError:
				old_rating = session.query(UserRating).filter(UserRating.rater == rater_slug).first()
				print('[migration] cannot create ' + author_slug + '`s rate from ' + rater_slug)
				print('[migration] concat rating value %d+%d=%d' % (old_rating.value, rating_entry['value'], old_rating.value + rating_entry['value']))
				old_rating.update({ 'value': old_rating.value + rating_entry['value'] })
				session.commit()
			except Exception as e:
				print(e)
	return ce
