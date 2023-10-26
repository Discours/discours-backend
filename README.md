# discoursio-api


- sqlalchemy
- redis
- ariadne
- starlette
- uvicorn

# Local development

Install deps first

on osx
```
brew install redis nginx postgres
brew services start redis
```

on debian/ubuntu
```
apt install redis nginx
```

First, install Postgres. Then you'll need some data, so migrate it:
```
createdb discoursio
python server.py migrate
```

Then run nginx, redis and API server
```
redis-server
pip install -r requirements.txt
python3 server.py dev
```

# pre-commit hook

```
pip install -r requirements-dev.txt
pre-commit install
```

# How to do an authorized request

Put the header 'Authorization' with token from signIn query or registerUser mutation.

# How to debug Ackee

Set ACKEE_TOKEN var
