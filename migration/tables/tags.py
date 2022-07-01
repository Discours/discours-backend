import json
from datetime import datetime
from orm.base import local_session
from orm import Topic, Community
from dateutil.parser import parse as date_parse

def migrate(entry, topics_by_oid):
	'''
	type Topic {
		slug: String! # ID
		createdBy: Int! # User
		createdAt: DateTime!
		title: String
		parents: [String] # NOTE: topic can have parent topics
		children: [String] # and children
	}
	'''
	if type(entry['createdAt']) == type(''):
		ts = date_parse(entry['createdAt'])
	else:
		ts = datetime.fromtimestamp(entry['createdAt']/1000)
	topic_dict = {
		'slug': entry['slug'],
		'oid': entry['_id'],
		# 'createdBy': entry['createdBy'],
		# 'createdAt': ts,
		'title': entry['title'].replace('&nbsp;', ' '), # .lower(),
		'children': [],
		'community' : Community.default_community.slug,
		'body' : entry.get('description','').replace('&nbsp;', ' ')
	}
	try:
		retopics = json.loads(open('migration/tables/replacements.json').read())
		with local_session() as session:
			slug = topics_by_oid.get(topic_dict['oid'], topic_dict)['slug']
			if slug:
				topic = session.query(Topic).filter(Topic.slug == slug).first()
				if not topic: 
					del topic_dict['oid']
					topic = Topic.create(**topic_dict)
				else:
					print(slug + ': ' + topic.title)
			else:
				print('not found topic: ' + slug)
				raise Exception
	except Exception as e:
		print(e)
		raise e
	topic_dict['oid'] = entry['_id']
	return topic_dict
