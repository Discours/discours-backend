from migration.html2md import Converter
from dateutil.parser import parse
from os.path import abspath
import json
from orm import Shout

users_dict = json.loads(open(abspath('migration/data/users.dict.json')).read())
users_dict['0'] = {'id': 99999 }

markdown = Converter()

type2layout = {
    'Article': 'article',
    'Literature': 'prose',
    'Music': 'music',
    'Video': 'video',
    'Image': 'image'
}

def migrate(entry):
    '''  
    type Shout {
        org_id: Int!
        slug: String!
        author: Int!
        body: String!
        createdAt: DateTime!
        updatedAt: DateTime!
        deletedAt: DateTime
        deletedBy: Int
        rating: Int
        ratigns: [Rating]
        published: Bool! 
        publishedAt: DateTime # if there is no published field - it is not published
        replyTo: String # another shout
        tags: [String] # actual values
        topics: [String] # topic-slugs, order has matter
        title: String
        versionOf: String
        visibleForRoles: [String] # role ids are strings
        visibleForUsers: [Int]
        views: Int
    }
    '''
    r = {
            'org_id': 0,
            'layout': type2layout[entry['type']],
            'title': entry['title'],
            'authors': [ users_dict[entry['createdBy']]['id'], ],
            'topics': [],
            'published': entry['published'],
            'views': entry['views'],
            'rating': entry['rating'],
            'ratings': []
        }
    r['slug'] = entry.get('slug')
    if not r['slug'] and entry.get('friendlySlugs') is not None:
        r['slug'] = entry['friendlySlugs']['slug'][0]['slug']
        if(r['slug'] is None):
            r['slug'] = entry['friendlySlugs'][0]['slug']
    if entry.get('image') is not None:
        r['cover'] = entry['image']['url']
    elif entry.get('thumborId') is not None:
        r['cover'] = 'https://discours.io/' + entry['thumborId']

    if entry.get('publishedAt') is not None:
        r['publishedAt'] = entry['publishedAt']
    if entry.get('createdAt') is not None:
        r['createdAt'] = entry['createdAt']
    if entry.get('updatedAt') is not None:
        r['updatedAt'] = entry['updatedAt']
    if entry.get('type') == 'Literature':
        r['body'] = entry['media'][0]['literatureBody']
    elif entry.get('type') == 'Video':
        r['body'] = '<ShoutVideo src=\"' + entry['media'][0]['youtubeId'] + '\" />'
    elif entry.get('type') == 'Music':
        r['body'] = '<ShoutMusic media={\"' + json.dumps(entry['media']) +'\"} />'
    else:
        r['body'] = '## ' + r['title']
    # TODO: compile md with graymatter
    open('migration/content/' + r['slug'] + '.md', 'w').write(mdfile)
    shout = Shout.create(**r.copy())
    r['id'] = shout['id']
    return r
