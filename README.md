# discours-backend-next

Tech stack:

 - pyjwt
 - redis
 - ariadne
 - starlette

# Local development

Install redis first, then start

'''
brew install redis
brew services start redis
'''

Then run API server

'''
pip3 install -r requirements.txt
python3 server.py
'''

# With Docker

TODO


# How to do an authorized request 

Put the header 'Auth' with token from signInQuery in requests.