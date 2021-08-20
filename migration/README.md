# discours-migration

First, put the `data` into this folder.

## Install

```sh
pipenv install -r requirements.txt
```

## Using

Put the unpacked mongodump to the `data` folder and operate with `pipenv shell && python`


1. get old data jsons 

```py
import bson2json

bson2json.json_tables() # creates all the needed data json from bson mongodump
```

2. migrate users

```py
import json
from migrations.users import migrate

data = json.loads(open('data/users.json').read())
newdata = {}

for u in data:
    try:
        newdata[u['_id']] = migrate(u)
    except:
        print('FAIL!')
        print(u)


```