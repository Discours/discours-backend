import json
from migration.tables.users import migrate as migrateUser
from migration.tables.content_items import migrate as migrateShout
from migration.tables.content_item_categories import migrate as migrateTopic
from migration.utils import DateTimeEncoder

def users(limit):
    print('migrating users...')
    data = json.loads(open('migration/data/users.json').read())
    newdata = {}
    counter = 0
    #try:
    for entry in data:
        oid = entry['_id']
        newdata[oid] = migrateUser(entry)
        counter += 1
        if counter > limit:
            break
    #except Exception:
    #    print(str(counter) + '/' + str(len(data)) + ' users entries were migrated')
    #    print('try to remove database first')
    open('migration/data/users.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    print(str(counter) + ' users entries were migrated')


def topics(limit):
    print('migrating topics...')
    data = json.loads(open('migration/data/content_item_categories.json').read())
    newdata = {}
    counter = 0
    try:
        for entry in data:
            oid = entry['_id']
            newdata[oid] = migrateTopic(entry)
            counter += 1
            if counter > limit:
                break
    except Exception:
        print(str(counter) + '/' + str(len(data)) + ' topics were migrated')
        print('try to remove database first')
    open('migration/data/topics.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    print(str(counter) + ' topics were migrated')

def shouts(limit):
    print('loading shouts...')
    counter = 0
    discoursAuthor = 0
    data = json.loads(open('migration/data/content_items.json').read())
    newdata = {}
    print(str(len(data)) + ' entries was loaded. now migrating...')
    errored = []

    for entry in data:
        try:
            oid = entry['_id']
            newdata[oid] = migrateShout(entry)
            counter += 1
            
            author = newdata[oid]['authors'][0]['slug']
            if author == 'discours':
                discoursAuthor += 1
            line = str(counter) + ': ' + newdata[oid]['slug'] + " @" + str(author)
            print(line)
            open('./shouts.id.log','a').write(line + '\n')
            if counter > limit:
                break
        except Exception:
            print(entry['_id'])
            errored.append(entry)
            raise Exception

    open('migration/data/shouts.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    print(str(counter) + ' shouts were migrated')
    print(str(discoursAuthor) + ' from them by @discours')
    print(str(len(errored)) + ' shouts without authors')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        limit = int(sys.argv[2])
        if sys.argv[1] == "users":
            users(limit)
        elif sys.argv[1] == "topics":
            topics(limit)
        elif sys.argv[1] == "shouts":
            shouts(limit)
        elif sys.argv[1] == "comments":
            comments(limit)
            pass
        elif sys.argv[1] == "all":
            topics(limit)
            users(limit)
            shouts(limit)
        elif sys.argv[1] == "bson":
            import migration.bson2json
            bson2json.json_tables()
    else:
        print('usage: python migrate.py <all|topics|users|shouts|comments> <stop_index>')