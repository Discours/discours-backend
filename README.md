# discoursio-api


- sqlalchemy
- redis
- ariadne
- starlette
- uvicorn

on osx
```
brew install redis nginx postgres
brew services start redis
```

on debian/ubuntu
```
apt install redis nginx
```

# Local development

Install deps first

```
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

Create database from backup
```
./restdb.sh
```

Start local server
```
python3 server.py dev
```

# How to do an authorized request

Put the header 'Authorization' with token from signIn query or registerUser mutation.

# How to debug Ackee

Set ACKEE_TOKEN var
