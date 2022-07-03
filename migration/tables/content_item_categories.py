from orm.base import local_session
from orm import Topic, Community
from dateutil.parser import parse as date_parse
import json
from migration.html2text import html2text
import sqlalchemy

def migrate(entry, topics_by_oid):
	'''
	type Topic {
		slug: String! # ID
		createdBy: Int! # User
		createdAt: DateTime!
		value: String
		children: [String] # children topic
	}
	'''
	topic_dict = {
		'slug': entry['slug'],
		'oid': entry['_id'],
		# 'createdBy': entry['createdBy'],
		# 'createdAt': date_parse(entry['createdAt']),
		'title': entry['title'].replace('&nbsp;', ' '), #.lower(),
		'children': [],
		'community' : Community.default_community.slug,
		'body' : html2text(entry.get('description', '').replace('&nbsp;', ' '))
	}
	retopics = json.loads(open('migration/tables/replacements.json').read())
	with local_session() as session:
		slug = topics_by_oid.get(topic_dict['oid'], topic_dict)['slug']
		if slug:
			slug = retopics.get(slug, slug)
			try:
				topic = session.query(Topic).filter(Topic.slug == slug).first()
				if not topic:
					del topic_dict['oid']
					topic = Topic.create(**topic_dict)
					# print('created')
				else:
					if len(topic.title) > len(topic_dict['title']) or \
						len(topic.body) < len(topic_dict['body']):
							topic.update({
								'slug': slug,
								'title':  topic_dict['title'] if len(topic.title) > len(topic_dict['title']) else topic.title,
								'body':  topic_dict['body'] if len(topic.body) < len(topic_dict['body']) else topic.body
							})
			except Exception as e:
				print('not found old topic: ' + slug)
		else:
			raise Exception
	topic_dict['oid'] = entry['_id']
	return topic_dict
