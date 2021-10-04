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
    return {
        'slug': entry['slug'],
        'createdBy': entry['createdBy'], # NOTE: uses an old user id
        'createdAt': entry['createdAt'],
        'title': entry['title'].lower(),
        'parents': [],
        'children': [],
        'old_id': entry['_id']
    }