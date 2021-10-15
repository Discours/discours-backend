from orm import User, Role, UserRating
import frontmatter
from dateutil.parser import parse
from migration.html2text import html2text
from orm.base import local_session

counter = 0

def migrate(entry, limit=668):
	'''

	type User {
		username: String! # email
		createdAt: DateTime!
		email: String
		password: String
		oauth: String # provider:token
		name: String # to display
		userpic: String
		links: [String]
		emailConfirmed: Boolean # should contain all emails too
		id: Int!
		muted: Boolean
		rating: Int
		roles: [Role]
		updatedAt: DateTime
		wasOnlineAt: DateTime
		ratings: [Rating]
		slug: String
		bio: String
		notifications: [Int]
	}

	'''
	res = {}
	res['old_id'] = entry['_id']
	res['password'] = entry['services']['password'].get('bcrypt', '')
	res['username'] = entry['emails'][0]['address']
	res['email'] = res['username']
	res['wasOnlineAt'] = parse(entry.get('loggedInAt', entry['createdAt']))
	res['emailConfirmed'] = entry['emails'][0]['verified']
	res['createdAt'] = parse(entry['createdAt'])
	res['rating'] = entry['rating'] # number
	res['roles'] = [] # entry['roles'] # roles by community
	res['ratings'] = [] # entry['ratings']
	res['notifications'] = []
	res['links'] = []
	res['muted'] = False
	res['bio'] = html2text(entry.get('bio', ''))
	res['name'] = 'anonymous'
	if not res['bio'].strip() or res['bio'] == '\n': del res['bio']
	if entry.get('profile'):
		# slug
		res['slug'] = entry['profile'].get('path')

		# userpic
		try: res['userpic'] = 'https://assets.discours.io/unsafe/100x/' + entry['profile']['thumborId']
		except KeyError:
			try: res['userpic'] = entry['profile']['image']['url']
			except KeyError: res['userpic'] = ''

		# name
		fn = entry['profile'].get('firstName', '')
		ln = entry['profile'].get('lastName', '')
		name = res['slug'] if res['slug'] else 'anonymous'
		name = fn if fn else name
		name = (name + ' ' + ln) if ln else name
		name = entry['profile']['path'].lower().replace(' ', '-') if len(name) < 2 else name
		res['name'] = name

		# links
		fb = entry['profile'].get('facebook', False)
		if fb:
			res['links'].append(fb)
		vk = entry['profile'].get('vkontakte', False)
		if vk:
			res['links'].append(vk)
		tr = entry['profile'].get('twitter', False)
		if tr:
			res['links'].append(tr)
		ws = entry['profile'].get('website', False)
		if ws:
			res['links'].append(ws)

	# some checks
	if not res['slug'] and len(res['links']) > 0: res['slug'] = res['links'][0].split('/')[-1]

	res['slug'] = res.get('slug', res['email'].split('@')[0])
	old = res['old_id']
	user = User.create(**res.copy())
	res['id'] = user.id
	res['ratings'] = []
	for user_rating_old in entry.get('ratings',[]):
		with local_session() as session: 
			rater = session.query(User).filter(old == user_rating_old['createdBy']).first()
			if rater:
				user_rating_dict = {
					'value': user_rating_old['value'],
					'rater_id': rater.id,
					'user_id': user.id
				}
				cts = user_rating_old.get('createdAt')
				if cts: user_rating_dict['createdAt'] = date_parse(cts)
				try:
					user_rating = UserRating.create(**user_rating_dict)
					res['ratings'].append(user_rating_dict)
				except Exception as e:
					print(comment_rating_dict)
					raise e
	return res
