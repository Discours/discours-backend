# discoursio-api

Tech stack:

- pyjwt
- redis
- ariadne
- starlette

# Local development 

Install redis and poetry (or any python env manager) first

on osx
```
brew install redis poetry
brew services start redis
```

on debian/ubuntu
```
apt install redis python-poetry
```

Then run API server

```
poetry install
poetry run python server.py
```

Also see `Dockerfile`

# How to do an authorized request

Put the header 'Auth' with token from signInQuery or registerQuery.

