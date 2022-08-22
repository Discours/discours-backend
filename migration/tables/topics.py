from logging import exception
from migration.extract import extract_md, html2text
from base.orm import local_session
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
	topic_dict['body'] = extract_md(html2text(body_orig), entry['_id'])
	with local_session() as session:
		slug = topic_dict['slug']
		t: Topic = session.query(Topic).filter(Topic.slug == slug).first() or Topic.create(**topic_d) or raise Exception('topic not created')  # type: ignore
		if t:
			if len(t.title) > len(topic_dict['title']): 
				Topic.update(t, {'title': topic_dict['title']})
			if len(t.body) < len(topic_dict['body']): 
				Topic.update(t, { 'body':  topic_dict['body'] })
			session.commit()
	# print(topic.__dict__)
	rt = t.__dict__.copy()
	del rt['_sa_instance_state']
	return rt
