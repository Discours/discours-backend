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
        parents: [String] # NOTE: topic can have parent topics
        children: [String] # and children
    }
    '''
    topic_dict = {
        'slug': entry['slug'],
        # 'createdBy': entry['createdBy'],
        # 'createdAt': date_parse(entry['createdAt']),
        'title': entry['title'].lower(),
        'parents': [],
        'children': [],
        'cat_id': entry['_id'],
        'community' : Community.default_community.slug
    }
    try:
        with local_session() as session:
            topic = session.query(Topic).filter(Topic.slug == entry['slug']).first()
            if not topic:
                topic = Topic.create(**topic_dict)
                topic_dict['id'] = topic.id
            return topic_dict
    except Exception as e:
        print(e)
        raise e
