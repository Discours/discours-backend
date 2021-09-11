from dateutil.parser import parse
from orm import User
from os.path import abspath
import frontmatter
import json
from orm import Shout
from bs4 import BeautifulSoup
from migration.html2text import html2text
from transliterate import translit
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from orm.base import local_session

users_dict = json.loads(open(abspath('migration/data/users.dict.json')).read())
users_dict['0'] = {
    'id': 9999999,
    'slug': 'discours',
    'viewname': 'Дискурс',
    'userpic': 'https://discours.io/images/logo-mini.svg'
    }

ts = datetime.now()

type2layout = {
    'Article': 'article',
    'Literature': 'prose',
    'Music': 'music',
    'Video': 'video',
    'Image': 'image'
}

def migrate(entry, limit=3626, start=0):
    '''  
    type Shout {
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
            'layout': type2layout[entry['type']],
            'title': entry['title'],
            'authors': [],
            'topics': [],
            'published': entry.get('published', False),
            'views': entry.get('views', 0),
            'rating': entry.get('rating', 0),
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
    if entry.get('updatedAt') is not None:
        r['updatedAt'] = parse(entry['updatedAt'])
    if entry.get('type') == 'Literature':
        media = entry.get('media', '')
        # print(media[0]['literatureBody'])
        if type(media) == list:
            body_orig = media[0].get('literatureBody', '')
            if body_orig == '':
                print('EMPTY BODY!')
            else:
                # body_html = str(BeautifulSoup(body_orig, features="html.parser"))
                # body = html2text(body_orig).replace('****', '**')
                r['old_id'] = entry.get('_id')
                r['body'] = body_orig
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
            print(entry.get('media', 'NO MEDIA!'))
            # raise Exception
        r['body'] = '<ShoutVideo src=\"' + videoUrl + '\" />' + html2text(m.get('body', '')) # FIXME
    elif entry.get('type') == 'Music':
        r['body'] = '<ShoutMusic media={\"' + json.dumps(entry['media']) +'\"} />' # FIXME

    if r.get('body') is None:
        body_orig = entry.get('body', '')
        body_html = BeautifulSoup(body_orig, features="html.parser")
        r['body'] = body_html # html2text(body_orig).replace('****', '**')
        r['old_id'] = entry.get('_id')
        
    body = r.get('body')
    user = None
    try:
        userdata = users_dict[entry['createdBy']]
        slug = userdata['slug']
        name = userdata['viewname']
        userpic = userdata['userpic']
    except KeyError:
        app = entry.get('application')
        if app is not None:
            authordata = {
                'username': app['email'],
                'email': app['email'],
                'viewname': app['name'],
                'bio': app.get('bio', ''),
                'emailConfirmed': False,
                'slug': translit(app['name'], 'ru', reversed=True).replace(' ', '-').lower(),
                'createdAt': ts,
                'wasOnlineAt': ts
            }
            try:
                user = User.create(**authordata)
            except IntegrityError:
                with local_session() as session:
                    user = session.query(User).filter(User.email == authordata['email']).first()
                    if user is None:
                        user = session.query(User).filter(User.slug == authordata['slug']).first()
                    
            slug = user.slug
            name = user.viewname
            userpic = user.userpic
        else:
            # no application, no author!
            slug = 'discours'
            name = 'Дискурс'
            userpic = 'https://discours.io/images/logo-mini.svg'
    with local_session() as session:
        user = session.query(User).filter(User.slug == slug).first()
    r['authors'].append({
        'slug': slug,
        'name': name,
        'pic': userpic
    })

    metadata = {}
    metadata['title'] = r.get('title')
    metadata['authors'] = r.get('authors')
    if r.get('cover', False):
        metadata['cover'] = r.get('cover')
    post = frontmatter.Post(body, **metadata)
    dumped = frontmatter.dumps(post)

    if entry['published']: 
        if r.get('old_id', None):
            ext = 'html'
            content = str(body).replace('<p></p>', '').replace('<p> </p>', '')
        else:
            ext = 'md'
            content = dumped
        open('migration/content/' + entry['type'].lower() + '/' + r['slug'] + '.' + ext, 'w').write(content)

    try:
        shout_dict = r.copy()
        shout_dict['authors'] = [user, ]
        if entry.get('createdAt') is not None:
            shout_dict['createdAt'] = parse(entry.get('createdAt'))
        else:
            shout_dict['createdAt'] = ts
        if entry.get('published'):
            if entry.get('publishedAt') is not None:
                shout_dict['publishedAt'] = parse(entry.get('publishedAt'))
            else:
                shout_dict['publishedAt'] = ts
        s = Shout.create(**shout_dict)
        r['id'] = s.id
    except:
        r['body'] = 'body moved'
        print(r)
        # print(s)
        raise Exception
    return r
