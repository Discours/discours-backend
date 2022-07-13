# discours-migration

First, put the `data` into this folder.

## Install

```sh
pipenv install -r requirements.txt
```

## Using

Put the unpacked mongodump to the `data` folder and operate with
`pipenv shell && python`
#### get old data jsons

```py
import bson2json

bson2json.json_tables() # creates all the needed data json from bson mongodump
```

#### migrate all

```sh
pipenv install
pipenv run python migrate.py all
```
#### or migrate all with mdx exports

```sh
pipenv install
pipenv run python migrate.py all mdx
```

Note: this will create db entries and it is not tolerant to existed unique
email.

#### or one shout by slug

```sh
pipenv run python migrate.py - <shout-slug>
```
