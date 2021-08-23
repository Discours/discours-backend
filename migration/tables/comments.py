# from html2md import Converter
import datetime

# markdown = Converter()

def migrate(entry):
    '''
    # is comment
    type Shout {
        org: String!
        slug: String!
        author: Int!
        body: String!
        createdAt: DateTime!
        updatedAt: DateTime!
        deletedAt: DateTime
        deletedBy: Int
        rating: Int
        published: DateTime # if there is no published field - it is not published
        replyTo: String # another shout
        tags: [String] # actual values
        topics: [String] # topic-slugs
        title: String
        versionOf: String
        visibleForRoles: [String] # role ids are strings
        visibleForUsers: [Int]
    }
    '''
    # TODO: implement comments migration
    return {
        'org': 'discours.io',
        'slug': entry['slug'],
        'createdAt': entry['createdAt'],
        'body': html2text(entry['body']),
        'replyTo': entry['']
    }