from html2text import html2text
import datetime

# markdown = Converter()

def migrate(entry):
    '''
    type Comment {
        id: Int!
        author: Int!
        body: String!
        replyTo: Int!
        createdAt: DateTime!
        updatedAt: DateTime
        shout: Int!
        deletedAt: DateTime
        deletedBy: Int
        rating: Int
        ratigns: [Rating]
        views: Int
        old_id: String
    }
    '''
    # TODO: implement comments migration
    return {
        'slug': entry['slug'],
        'createdAt': entry['createdAt'],
        'body': html2text(entry['body']),
        'replyTo': entry['']
    }