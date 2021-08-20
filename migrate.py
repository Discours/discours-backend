import json
from migration.tables.users import migrate as migrateUser
from migration.tables.content_items import migrate as migrateShout
from migration.tables.content_item_categories import migrate as migrateTopic
from migration.utils import DateTimeEncoder

def users():
    print('migrating users...')
    data = json.loads(open('migration/data/users.json').read())
    newdata = {}
    counter = 0
    #try:
    for entry in data:
        oid = entry['_id']
        newdata[oid] = migrateUser(entry)
        counter += 1
    #except Exception:
    #    print(str(counter) + '/' + str(len(data)) + ' users entries were migrated')
    #    print('try to remove database first')
    open('migration/data/users.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    print(str(counter) + ' users entries were migrated')


def topics():
    print('migrating topics...')
    data = json.loads(open('migration/data/content_item_categories.json').read())
    newdata = {}
    counter = 0
    try:
        for entry in data:
            oid = entry['_id']
            newdata[oid] = migrateTopic(entry)
            counter += 1
    except Exception:
        print(str(counter) + '/' + str(len(data)) + ' topics were migrated')
        print('try to remove database first')
    open('migration/data/topics.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    print(str(counter) + ' topics were migrated')

def shouts():
    print('migrating shouts...')
    counter = 0
    data = json.loads(open('migration/data/content_items.json').read())
    newdata = {}

    for entry in data:
        oid = entry['_id']
        newdata[oid] = migrateShout(entry)
        counter += 1
        print(str(counter) + ': ' + newdata['slug'])
        if counter > 9:
            break

    open('migration/data/shouts.dict.json','w').write( json.dumps(newdata, cls=DateTimeEncoder) )
    print(str(counter) + ' shouts were migrated')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "users":
            users()
        elif sys.argv[1] == "topics":
            topics()
        elif sys.argv[1] == "shouts":
            shouts()
        elif sys.argv[1] == "comments":
            # comments()
            pass
        elif sys.argv[1] == "all":
            topics()
            users()
            shouts()
        elif sys.argv[1] == "bson":
            import migration.bson2json
            bson2json.json_tables()
    else:
        print('usage: python migrate.py <all|topics|users|shouts|comments>')