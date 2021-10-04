def migrate(entry):
    ```
    type Topic {
        slug: String! # ID
        createdBy: Int! # User
        createdAt: DateTime!
        value: String
        parents: [String] # NOTE: topic can have parent topics
        children: [String] # and children
    }
    ```
    creator = get_new_user_id(entry['createdBy'])
    return {
        'slug': entry['slug'],
        'createdBy': creator_id, # NOTE: uses an old user id
        'createdAt': entry['createdAt'],
        'title': entry['value'].lower(),
        'parents': [],
        'children': []
    }