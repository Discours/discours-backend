# discoursio-api

Tech stack:

- pyjwt
- redis
- ariadne
- starlette

# Local development 

Install deps first

on osx
```
brew install redis nginx
brew services start redis
```

on debian/ubuntu
```
apt install redis nginx
```

First, you'll need some data
```

psql -U postgres
> create database discoursio;
> \q
python server.py migrate
```

Then run nginx, redis and API server
```
redis-server
pip install -r requirements.txt
python3 server.py dev
```

# How to do an authorized request

Put the header 'Auth' with token from signInQuery or registerQuery.

