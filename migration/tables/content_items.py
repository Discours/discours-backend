from dateutil.parser import parse
from os.path import abspath
import frontmatter
import json
from orm import Shout, Comment, Topic, ShoutRating, User #, TODO: CommentRating
from bs4 import BeautifulSoup
from migration.html2text import html2text
from migration.tables.comments import migrate as migrateComment
from transliterate import translit
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from orm.base import local_session

users_dict = json.loads(open(abspath('migration/data/users.dict.json')).read())
print(str(len(users_dict.items())) + ' users loaded')
topics_dict = json.loads(open(abspath('migration/data/topics.dict.json')).read()) # old_id keyed
print(str(len(topics_dict.items())) + ' topics loaded')
comments_data = json.loads(open(abspath('migration/data/comments.json')).read())
print(str(len(comments_data)) + ' comments loaded')
comments_by_post = {}
for comment in comments_data:
    p = comment['contentItem']
    comments_by_post[p] = comments_by_post.get(p, [])
    comments_by_post[p].append(comment)
    
users_dict['0'] = {
    'id': 9999999,
    'slug': 'discours',
    'name': 'Дискурс',
    'userpic': 'https://discours.io/images/logo-mini.svg',
    'createdAt': '2016-03-05 22:22:00.350000'
}

ts = datetime.now()

type2layout = {
    'Article': 'article',
    'Literature': 'prose',
    'Music': 'music',
    'Video': 'video',
    'Image': 'image'
}


def get_metadata(r):
    metadata = {}
    metadata['title'] = r.get('title')
    metadata['authors'] = r.get('authors')
    metadata['createdAt'] = r.get('createdAt', ts)
    metadata['layout'] = r['layout']
    metadata['topics'] = r['topics']
    if r.get('cover', False):
        metadata['cover'] = r.get('cover')
    return metadata

def migrate(entry):
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
    content = ''
    r = {
        'layout': type2layout[entry['type']],
        'title': entry['title'],
        'community': 0,
        'authors': [],
        'topics': [],
        'published': entry.get('published', False),
        'views': entry.get('views', 0),
        'rating': entry.get('rating', 0),
        'ratings': [],
        'comments': [],
        'createdAt': entry.get('createdAt', '2016-03-05 22:22:00.350000')
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
    try:
      r['topics'].append(topics_dict[entry['category']]['slug'])
    except Exception:
      print(entry['category'])
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
                body_html = str(BeautifulSoup(
                    body_orig, features="html.parser"))
                r['body'] = html2text(body_html)
        else:
            print(r['slug'] + ': literature has no media')
    elif entry.get('type') == 'Video':
      m = entry['media'][0]
      yt = m.get('youtubeId', '')
      vm = m.get('vimeoId', '')
      video_url = 'https://www.youtube.com/watch?v=' + yt if yt else '#'
      if video_url == '#':
          video_url = 'https://vimeo.com/' + vm if vm else '#'
      if video_url == '#':
          print(entry.get('media', 'NO MEDIA!'))
          # raise Exception
      r['body'] = '<ShoutVideo src=\"' + video_url + \
            '\" />' + html2text(m.get('body', ''))  # FIXME
    elif entry.get('type') == 'Music':
        r['body'] = '<ShoutMusic media={\"' + \
            json.dumps(entry['media']) + '\"} />'  # FIXME
    if r.get('body') is None:
        body_orig = entry.get('body', '')
        body_html = str(BeautifulSoup(body_orig, features="html.parser"))
        r['body'] = html2text(body_html)
    body = r.get('body', '')
    r['old_id'] = entry.get('_id')
    user = None
    try:
        userdata = users_dict.get(entry['createdBy'], users_dict['0'])
        slug = userdata['slug']
        name = userdata['name']
        userpic = userdata['userpic']
    except KeyError:
        app = entry.get('application')
        if app is not None:
            authordata = {
                'username': app['email'],
                'email': app['email'],
                'name': app['name'],
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
                    user = session.query(User).filter(
                        User.email == authordata['email']).first()
                    if user is None:
                        user = session.query(User).filter(
                            User.slug == authordata['slug']).first()
            slug = user['slug']
            name = user['name']
            userpic = user['userpic']
        else:
            # no application, no author!
            slug = 'discours'
            name = 'Дискурс'
            userpic = 'https://discours.io/images/logo-mini.svg'
    with local_session() as session:
        user = session.query(User).filter(User.slug == slug).first()
    r['authors'].append({
        'id': user.id,
        'slug': slug,
        'name': name,
        'userpic': userpic
    })

    r['layout'] = type2layout[entry['type']]

    metadata = get_metadata(r)
    content = frontmatter.dumps(frontmatter.Post(body, **metadata))

    if entry['published']:
        ext = 'md'
        open('migration/content/' +
            r['layout'] + '/' + r['slug'] + '.' + ext, 'w').write(content)
        try:
            shout_dict = r.copy()
            shout_dict['authors'] = [user, ]
            if entry.get('createdAt') is not None:
                shout_dict['createdAt'] = parse(r.get('createdAt'))
            else:
                shout_dict['createdAt'] = ts
            if entry.get('published'):
                if entry.get('publishedAt') is not None:
                    shout_dict['publishedAt'] = parse(entry.get('publishedAt'))
                else:
                    shout_dict['publishedAt'] = ts
            del shout_dict['published']

            try:
                topic_slugs = shout_dict['topics']
                del shout_dict['topics'] # FIXME: AttributeError: 'str' object has no attribute '_sa_instance_state'
                del shout_dict['views'] # FIXME: TypeError: 'views' is an invalid keyword argument for Shout
                del shout_dict['rating'] # FIXME: TypeError: 'rating' is an invalid keyword argument for Shout
                del shout_dict['ratings']
                s = Shout.create(**shout_dict) 
                r['id'] = s.id
                
                if len(entry.get('ratings', [])) > 0:
                    # TODO: adding shout ratings
                    '''
                    shout_dict['ratings'] = []
                    for shout_rating_old in entry['ratings']:
                        shout_rating = ShoutRating.create(
                            rater_id = users_dict[shout_rating_old['createdBy']]['id'],
                            shout_id = s.id,
                            value = shout_rating_old['value']
                        )
                        shout.ratings.append(shout_rating.id)
                    '''
                # adding topics to created shout
                for topic_slug in topic_slugs:
                        if not topic: 
                            topic_dict = topics_dict.get(topic_slug)
                            if topic_dict:
                                topic = Topic.create(**topic_dict)
                        shout.topics = [ topic, ]
                        shout.save()
            except Exception as e:
                r['error'] = 'db error'
                # pass
                raise e
        except Exception as e:
            if not r['body']: r['body'] = 'body moved'
            raise e
    return r
