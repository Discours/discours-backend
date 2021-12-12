from orm.base import local_session
from orm import Topic, Community
from dateutil.parser import parse as date_parse

def migrate(entry):
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
        # 'createdBy': entry['createdBy'],
        # 'createdAt': date_parse(entry['createdAt']),
        'title': entry['title'].lower(),
        'children': [],
        'community' : Community.default_community.slug
    }
    try:
        with local_session() as session:
            topic = session.query(Topic).filter(Topic.slug == entry['slug']).first()
            if not topic:
                topic = Topic.create(**topic_dict)
    except Exception as e:
        print(e)
        raise e
    topic_dict['cat_id'] = entry['_id']
    return topic_dict
