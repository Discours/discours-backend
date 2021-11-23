# discoursio-api

Tech stack:

- pyjwt
- redis
- ariadne
- starlette

# Local development

Install redis and pipenv first

```
brew install redis pipenv
brew services start redis
```

Create certificate files

```sh
./create_crt.sh
```

Then run API server

```
pipenv install
pipenv run python server.py
```

Also see `Dockerfile`

# How to do an authorized request

Put the header 'Auth' with token from signInQuery or registerQuery.
