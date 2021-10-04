import json
from migration.tables.users import migrate as migrateUser
from migration.tables.content_items import migrate as migrateShout
from migration.tables.content_item_categories import migrate as migrateTopic
from migration.utils import DateTimeEncoder
from orm import Community

def users(limit):
    print('migrating users...')
    data = json.loads(open('migration/data/users.json').read())
    newdata = {}
    exportData = {}
    counter = 0
    # limit = 100
    #try:
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
        exportData[user['slug']] = user
        counter += 1
        if counter > limit:
            break
    #except Exception:
    #    print(str(counter) + '/' + str(len(data)) + ' users entries were migrated')
    #    print('try to remove database first')
    open('migration/data/users.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    open('../src/data/authors.json','w').write( json.dumps(exportData, cls=DateTimeEncoder) )
    print(str(counter) + ' users entries were migrated')


def topics():
    print('migrating topics...')
    data = json.loads(open('migration/data/content_item_categories.json').read())
    newdata = {}
    exportData = {}
    counter = 0
    try:
        for entry in data:
            oid = entry['_id']
            newdata[oid] = migrateTopic(entry)
            exportData[entry['slug']] = newdata[oid]
            counter += 1
    except Exception:
        print(str(counter) + '/' + str(len(data)) + ' topics were migrated')
        print('try to remove database first')
    open('migration/data/topics.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    open('../src/data/topics.json','w').write( json.dumps(exportData, cls=DateTimeEncoder) )
    print(str(counter) + ' topics were migrated')

def shouts(limit):
    print('loading shouts...')
    counter = 0
    discoursAuthor = 0
    data = json.loads(open('migration/data/content_items.json').read())
    newdata = {}
    print(str(len(data)) + ' entries loaded. now migrating...')
    errored = []
    exportData = {}
    for entry in data:
        try:
            oid = entry['_id']
            shout = migrateShout(entry)
            newdata[oid] = shout
            author = newdata[oid]['authors'][0]['slug']
            line = str(counter) + ': ' + newdata[oid]['slug'] + " @" + str(author)
            if shout['layout'] == 'article':
                counter += 1
                exportData[shout['slug']] = shout
                print(line)
            # counter += 1
            if author == 'discours.io':
                discoursAuthor += 1
            open('./shouts.id.log','a').write(line + '\n')
            if counter > limit:
                break
        except Exception:
            print(entry['_id'])
            errored.append(entry)
            raise Exception

    open('migration/data/shouts.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    open('../src/data/articles.json','w').write( json.dumps(exportData, cls=DateTimeEncoder) )
    print(str(counter) + ' shouts were migrated')
    print(str(discoursAuthor) + ' from them by @discours.io')
    print(str(len(errored)) + ' shouts without authors')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "users":
            users(668)
        elif sys.argv[1] == "topics":
            topics()
        elif sys.argv[1] == "shouts":
            Community.create(**{
                'slug': 'discours.io',
                'name': 'Дискурс',
                'pic': 'https://discours.io/images/logo-min.svg',
                'createdBy': '0',
                'createdAt': ts
                })
            shouts(3626)
        elif sys.argv[1] == "all":
            topics()
            users(668)
            shouts(3626)
        elif sys.argv[1] == "bson":
            import migration.bson2json
            bson2json.json_tables()
    else:
        print('usage: python migrate.py <all|topics|users|shouts|comments>')