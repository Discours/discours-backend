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

Then run nginx, redis and API server

```
redis-server

cp nginx.conf /usr/local/etc/nginx/.
nginx -s reload

pip install -r requirements.txt
python server.py
python server.py inbox
```

# How to do an authorized request

Put the header 'Auth' with token from signInQuery or registerQuery.

