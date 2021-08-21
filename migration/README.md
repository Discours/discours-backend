# discours-migration

First, put the `data` into this folder.

## Install

```sh
pipenv install -r requirements.txt
```

## Using

Put the unpacked mongodump to the `data` folder and operate with
`pipenv shell && python`

1. get old data jsons

```py
import bson2json

bson2json.json_tables() # creates all the needed data json from bson mongodump
```

2. migrate users

```sh
pipenv run python migrate.py users
```

Note: this will create db entries and it is not tolerant to existed unique
email.

3. then topics and shouts

```sh
pipenv run python migrate.py topics
pipenv run python migrate.py shouts
```

Now you got the \*.dict.json files which contain all the data with old and
new(!) ids.
