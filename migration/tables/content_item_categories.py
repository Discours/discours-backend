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
        'createdBy': entry['createdBy'], # NOTE: uses an old user id
        'createdAt': entry['createdAt'],
        'title': entry['title'].lower(),
        'parents': [],
        'children': [],
        'old_id': entry['_id']
    }
    
    with local_session() as session:
        topic = session.query(Topic).filter(Topic.slug == topic_slug).first()
        if not topic:
            topic = Topic.create(**topic_dict)
            topic_dict['id'] = topic.id
        return topic_dict