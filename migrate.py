''' cmd managed migration '''
import json
import base64
import re
import frontmatter
from migration.tables.users import migrate as migrateUser
from migration.tables.content_items import get_metadata, migrate as migrateShout
from migration.tables.content_item_categories import migrate as migrateCategory
from migration.tables.tags import migrate as migrateTag
from migration.utils import DateTimeEncoder
from orm import Community


IMG_REGEX = r"\!\[(.*?)\]\((data\:image\/(png|jpeg|jpg);base64\,(.*?))\)"
OLD_DATE = '2016-03-05 22:22:00.350000'


def extract_images(article):
    ''' extract b64 encoded images from markdown in article body '''
    body = article['body']
    images = []
    matches = re.finditer(IMG_REGEX, body, re.IGNORECASE | re.MULTILINE)
    for i, match in enumerate(matches, start=1):
        ext = match.group(3)
        link = '/static/upload/image-' + \
            article['old_id'] + str(i) + '.' + ext
        img = match.group(4)
        if img not in images:
          open('..' + link, 'wb').write(base64.b64decode(img))
          images.append(img)
        body = body.replace(match.group(2), link)
        print(link)
    article['body'] = body
    return article


def users():
    ''' migrating users first '''
    print('migrating users...')
    newdata = {}
    data = json.loads(open('migration/data/users.json').read())
    counter = 0
    export_data = {}
    for entry in data:
        oid = entry['_id']
        user = migrateUser(entry)
        newdata[oid] = user
        del user['password']
        del user['notifications']
        # del user['oauth']
        del user['emailConfirmed']
        del user['username']
        del user['email']
        export_data[user['slug']] = user
        counter += 1
    export_list = sorted(export_data.items(),
                        key=lambda item: item[1]['rating'])[-10:]
    open('migration/data/users.dict.json',
         'w').write(json.dumps(newdata, cls=DateTimeEncoder))  # NOTE: by old_id
    open('../src/data/authors.json', 'w').write(json.dumps(dict(export_list),
                                                           cls=DateTimeEncoder,
                                                           indent=4,
                                                           sort_keys=True,
                                                           ensure_ascii=False))
    print(str(len(newdata.items())) + ' user accounts were migrated')
    print(str(len(export_list)) + ' authors were exported')


def topics():
    ''' topics from categories and tags '''
    print('migrating topics...')
    cat_data = json.loads(
        open('migration/data/content_item_categories.json').read())
    # tag_data = json.loads(open('migration/data/tags.json').read())
    new_data = {}
    old_data = {}
    counter = 0
    try:
        for cat in cat_data:
            topic = migrateCategory(cat)
            old_data[topic['old_id']] = topic
            new_data[topic['slug']] = topic
            counter += 1
    except Exception:
        print('cats exception, try to remove database first')
    '''
    try:
        for tag in tag_data:
            topic = migrateTag(tag)
            newdata[topic['slug']] = topic
            counter += 1
    except Exception:
        print('tags exception, try to remove database first')
        raise Exception
    '''
    export_list = sorted(new_data.items(), key=lambda item: str(
        item[1]['createdAt']))
    open('migration/data/topics.dict.json',
         'w').write(json.dumps(old_data, cls=DateTimeEncoder))
    open('../src/data/topics.json', 'w').write(json.dumps(dict(export_list),
                                                          cls=DateTimeEncoder,
                                                          indent=4,
                                                          sort_keys=True,
                                                          ensure_ascii=False))
    print(str(counter) + ' from ' + str(len(cat_data)) +
          #' tags and ' + str(len(tag_data)) +
          ' cats were migrated')
    print(str(len(export_list)) + ' topics were exported')


def shouts():
    ''' migrating content items one by one '''
    print('loading shouts...')
    counter = 0
    discours_author = 0
    content_data = json.loads(open('migration/data/content_items.json').read())
    # content_dict = { x['_id']:x for x in content_data }
    newdata = {}
    print(str(len(content_data)) + ' entries loaded. now migrating...')
    errored = []
    for entry in content_data:
        try:
            shout = migrateShout(entry)
            newdata[shout['slug']] = shout
            author = newdata[shout['slug']]['authors'][0]['slug']
            line = str(counter+1) + ': ' + shout['slug'] + " @" + str(author)
            print(line)
            counter += 1
            if author == 'discours':
                discours_author += 1
            open('./shouts.id.log', 'a').write(line + '\n')
        except Exception:
            print(entry['_id'])
            errored.append(entry)
            raise Exception(" error")
    try:
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else len(content_data)
    except ValueError:
        limit = len(content_data)
    open('migration/data/shouts.dict.json',
         'w').write(json.dumps(newdata, cls=DateTimeEncoder))
    print(str(counter) + '/' + str(len(content_data)) +
          ' content items were migrated')
    print(str(discours_author) + ' from them by @discours')

def export_shouts(limit):
    print('reading json...')
    newdata = json.loads(open('migration/data/shouts.dict.json', 'r').read())
    print(str(len(newdata.keys())) + ' shouts loaded')
    content_data = json.loads(open('migration/data/content_items.json').read())
    content_dict = { x['_id']:x for x in content_data }
    users_old = json.loads(open('migration/data/users.dict.json').read())
    export_authors = json.loads(open('../src/data/authors.json').read())
    print(str(len(export_authors.items())) + ' pre-exported authors loaded')
    users_slug = { u['slug']: u for old_id, u in users_old.items()}
    print(str(len(users_slug.items())) + ' users loaded')

    export_list = [i for i in newdata.items() if i[1]['layout'] == 'article' and i[1]['published']]
    export_list = sorted(export_list, key=lambda item: item[1]['createdAt'] or OLD_DATE, reverse=True)
    print(str(len(export_list)) + ' filtered')

    export_list = export_list[:limit or len(export_list)]
    export_clean = {}
    for (slug, article) in export_list:
        if article['layout'] == 'article':
            for author in article['authors']:
              export_authors[author['slug']] = users_slug[author['slug']]
            export_clean[article['slug']] = extract_images(article)
            metadata = get_metadata(article)
            content = frontmatter.dumps(frontmatter.Post(article['body'], **metadata))
            open('../content/discours.io/'+slug+'.md', 'w').write(content)
            # print(slug)
            open('../content/discours.io/'+slug+'.html', 'w').write(content_dict[article['old_id']]['body'])
    open('../src/data/articles.json', 'w').write(json.dumps(dict(export_clean),
                                                            cls=DateTimeEncoder,
                                                            indent=4,
                                                            sort_keys=True,
                                                            ensure_ascii=False))
    print(str(len(export_clean.items())) + ' articles exported')
    open('../src/data/authors.json', 'w').write(json.dumps(export_authors,
                                                           cls=DateTimeEncoder,
                                                           indent=4,
                                                           sort_keys=True,
                                                           ensure_ascii=False))
    print(str(len(export_authors.items())) + ' total authors exported')

def export_slug(slug):
    shouts_dict = json.loads(open('migration/data/shouts.dict.json').read())
    print(str(len(shouts_dict.items())) + ' shouts loaded')
    users_old = json.loads(open('migration/data/users.dict.json').read())
    print(str(len(users_old.items())) + ' users loaded')
    users_dict = { x[1]['slug']:x for x in users_old.items() }
    exported_authors = json.loads(open('../src/data/authors.json').read())
    print(str(len(exported_authors.items())) + ' authors were exported before')
    exported_articles = json.loads(open('../src/data/articles.json').read())
    print(str(len(exported_articles.items())) + ' articles were exported before')
    shout = shouts_dict.get(slug, None)
    author = users_dict.get(shout['authors'][0]['slug'], None)
    exported_authors.update({shout['authors'][0]['slug']: author})
    exported_articles.update({shout['slug']: shout})
    print(shout)
    open('../src/data/articles.json', 'w').write(json.dumps(exported_articles,
                                                           cls=DateTimeEncoder,
                                                           indent=4,
                                                           sort_keys=True,
                                                           ensure_ascii=False))
    open('../src/data/authors.json', 'w').write(json.dumps(exported_authors,
                                                           cls=DateTimeEncoder,
                                                           indent=4,
                                                           sort_keys=True,
                                                           ensure_ascii=False))
    print('exported.')
    

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "users":
            users()
        elif sys.argv[1] == "topics":
            topics()
        elif sys.argv[1] == "shouts":
            try:
                Community.create(**{
                    'slug': 'discours.io',
                    'name': 'Дискурс',
                    'pic': 'https://discours.io/images/logo-min.svg',
                    'createdBy': '0',
                    'createdAt': OLD_DATE
                })
            except Exception:
                pass
            shouts()
        elif sys.argv[1] == "export_shouts":
          limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
          export_shouts(limit)
        elif sys.argv[1] == "all":
            users()
            topics()
            shouts()
        elif sys.argv[1] == "bson":
            from migration import bson2json
            bson2json.json_tables()
        elif sys.argv[1] == 'slug':
            export_slug(sys.argv[2])
    else:
        print('usage: python migrate.py <bson|slug|topics|users|shouts|export_shouts [num]|slug [str]|all>')
