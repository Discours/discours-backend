from migration.extract import extract, html2text
from orm.base import local_session
from orm import Topic, Community

def migrate(entry):
	body_orig = entry.get('description', '').replace('&nbsp;', ' ')
	topic_dict = {
		'slug': entry['slug'],
		'oid': entry['_id'],
		'title': entry['title'].replace('&nbsp;', ' '), #.lower(),
		'children': [],
		'community' : Community.default_community.slug
	}
	topic_dict['body'] = extract(html2text(body_orig), entry['_id'])
	with local_session() as session:
		slug = topic_dict['slug']
		topic = session.query(Topic).filter(Topic.slug == slug).first()
		if not topic: 
			topic = Topic.create(**topic_dict)
		if len(topic.title) > len(topic_dict['title']):
			topic.update({ 'title':  topic_dict['title'] })
		if len(topic.body) < len(topic_dict['body']):
			topic.update({ 'body':  topic_dict['body'] })
		session.commit()
	# print(topic.__dict__)
	rt = topic.__dict__.copy()
	del rt['_sa_instance_state']
	return rt
