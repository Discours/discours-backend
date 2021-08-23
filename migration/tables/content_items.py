# from migration.html2md import Converter
from dateutil.parser import parse
from os.path import abspath
import frontmatter
import json
from orm import Shout
from bs4 import BeautifulSoup
from migration.html2text import html2text

users_dict = json.loads(open(abspath('migration/data/users.dict.json')).read())
users_dict['0'] = {'id': 9999999, 'slug': 'discours', 'viewname': 'Дискурс' }

# markdown = Converter()

type2layout = {
    'Article': 'article',
    'Literature': 'prose',
    'Music': 'music',
    'Video': 'video',
    'Image': 'image'
}

def migrate(entry, data=users_dict):
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
    try:
        author = data[entry['createdBy']]
    except KeyError:
        author = data['0']

    # print(author)
    r = {
            'org_id': 0,
            'layout': type2layout[entry['type']],
            'title': entry['title'],
            'authors': [ { 'slug': author['slug'], 'name': author['viewname'], 'pic': author.get('userpic', '') }, ],
            'topics': [],
            'published': entry['published'],
            'views': entry['views'],
            'rating': entry['rating'],
            'ratings': []
        }
    r['slug'] = entry.get('slug', '')
    body_orig = entry.get('body', '')
    if not r['slug'] and entry.get('friendlySlugs') is not None:
        r['slug'] = entry['friendlySlugs']['slug'][0]['slug']
        if(r['slug'] is None):
            r['slug'] = entry['friendlySlugs'][0]['slug']
    if not r['slug']:
        print('NO SLUG ERROR')
        # print(entry)
        raise Exception
    if entry.get('image') is not None:
        r['cover'] = entry['image']['url']
    if entry.get('thumborId') is not None:
        r['cover'] = 'https://assets.discours.io/unsafe/1600x/' + entry['thumborId']
    if entry.get('publishedAt') is not None:
        r['publishedAt'] = entry['publishedAt']
    if entry.get('createdAt') is not None:
        r['createdAt'] = entry['createdAt']
    if entry.get('updatedAt') is not None:
        r['updatedAt'] = entry['updatedAt']
    if entry.get('type') == 'Literature':
        media = entry.get('media', '')
        # print(media[0]['literatureBody'])
        if type(media) == list:
            body_orig = media[0].get('literatureBody', '')
            if body_orig == '':
                print('EMPTY BODY!')
            else:
                # body_html = str(BeautifulSoup(body_orig, features="html.parser"))
                #markdown.feed(body_html)
                body = html2text(body_orig).replace('****', '**')
                r['body'] = body
                # r['body2'] = markdown.md_file
        else:
            print(r['slug'] + ': literature has no media')
    elif entry.get('type') == 'Video':
        m = entry['media'][0]
        yt = m.get('youtubeId', '')
        vm = m.get('vimeoId', '')
        videoUrl = 'https://www.youtube.com/watch?v=' + yt if yt else '#'
        if videoUrl == '#':
            videoUrl = 'https://vimeo.com/' + vm if vm else '#'
        if videoUrl == '#':
            print(m)
            # raise Exception
        r['body'] = '<ShoutVideo src=\"' + videoUrl + '\" />' + html2text(m.get('body', '')) # FIXME
    elif entry.get('type') == 'Music':
        r['body'] = '<ShoutMusic media={\"' + json.dumps(entry['media']) +'\"} />' # FIXME

    if r.get('body') is None:
        body_orig = entry.get('body', '')
        # body_html = BeautifulSoup(body_orig, features="html.parser")
        r['body'] = html2text(body_orig).replace('****', '**')
        # markdown.feed(body_html)
        # r['body2'] = markdown.md_file
    if not r['body']:
        r['body'] = entry.get('body')
    metadata = {}
    metadata['title'] = r.get('title')
    metadata['authors'] = r.get('authors')
    if r.get('cover', False):
        metadata['cover'] = r.get('cover')
    body = r.get('body')
    post = frontmatter.Post(body, **metadata)
    dumped = frontmatter.dumps(post)
    # raise Exception

    open('migration/content/' + entry['type'].lower() + '/' + r['slug'] + '.md', 'w').write(dumped)
    # open('migration/content/' + entry['type'].lower() + '/' + r['slug'] + '.my.md', 'w').write(r['body2'])
    #if body_orig:
    #    open('migration/content/' + entry['type'].lower() + '/' + r['slug'] + '.html', 'w').write(body_orig)
    #markdown.related_data = []
    #markdown.md_file = ''
    #markdown.reset()
    r['body'] = dumped
    # shout = Shout.create(**r.copy())
    # r['id'] = shout['id']
    return r
