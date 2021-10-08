''' cmd managed migration '''
import json
import base64
import re
from migration.tables.users import migrate as migrateUser
from migration.tables.content_items import migrate as migrateShout
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
    tag_data = json.loads(open('migration/data/tags.json').read())
    newdata = {}
    counter = 0
    try:
        for cat in cat_data:
            topic = migrateCategory(cat)
            newdata[topic['slug']] = topic
            counter += 1
    except Exception:
        print('cats exception, try to remove database first')
    try:
        for tag in tag_data:
            topic = migrateTag(tag)
            newdata[topic['slug']] = topic
            counter += 1
    except Exception:
        print('tags exception, try to remove database first')
        raise Exception
    export_list = sorted(newdata.items(), key=lambda item: str(
        item[1]['createdAt']))[-10:]
    open('migration/data/topics.dict.json',
         'w').write(json.dumps(newdata, cls=DateTimeEncoder))
    open('../src/data/topics.json', 'w').write(json.dumps(dict(export_list),
                                                          cls=DateTimeEncoder, indent=4, sort_keys=True, ensure_ascii=False))
    print(str(counter) + ' from ' + str(len(cat_data)) +
          ' tags and ' + str(len(tag_data)) + ' cats were migrated')
    print(str(len(export_list)) + ' topics were exported')


def shouts():
    ''' migrating content items one by one '''
    print('loading shouts...')
    counter = 0
    discours_author = 0
    content_data = json.loads(open('migration/data/content_items.json').read())
    newdata = {}
    print(str(len(content_data)) + ' entries loaded. now migrating...')
    errored = []
    for entry in content_data:
        try:
            (shout, content) = migrateShout(entry)
            newdata[shout['slug']] = shout
            author = newdata[shout['slug']]['authors'][0]['slug']
            line = str(counter+1) + ': ' + shout['slug'] + " @" + str(author)
            print(line)
            counter += 1
            if author == 'discours.io':
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
    export_list = sorted(newdata.items(
    ), key=lambda item: item[1]['createdAt'] if item[1]['layout'] == 'article' else OLD_DATE)[:limit]
    export_clean = {}
    for slug, a in dict(export_list).items():
        export_clean[slug] = extract_images(a)
        open('../content/discours.io/'+slug+'.md', 'w').write(content)
    open('migration/data/shouts.dict.json',
         'w').write(json.dumps(newdata, cls=DateTimeEncoder))
    open('../src/data/articles.json', 'w').write(json.dumps(dict(export_clean),
                                                            cls=DateTimeEncoder,
                                                            indent=4,
                                                            sort_keys=True,
                                                            ensure_ascii=False))
    print(str(counter) + '/' + str(len(content_data)) +
          ' content items were migrated')
    print(str(len(export_list)) + ' shouts were exported')
    print(str(discours_author) + ' from them by @discours.io')


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
        elif sys.argv[1] == "all":
            users()
            topics()
            shouts()
        elif sys.argv[1] == "bson":
            from migration import bson2json
            bson2json.json_tables()
    else:
        print('usage: python migrate.py <bson|all|topics|users|shouts>')
