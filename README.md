# discours-backend-next

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

Then run API server

```
pipenv shell
python3 server.py
```

# With Docker

TODO


# How to do an authorized request 

Put the header 'Auth' with token from signInQuery in requests.