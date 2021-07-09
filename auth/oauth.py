from authlib.integrations.starlette_client import OAuth
from starlette.responses import PlainTextResponse

from auth.authorize import Authorize
from auth.identity import Identity

oauth = OAuth()

oauth.register(
	name='facebook',
	client_id='222122999761250',
	client_secret='',
	access_token_url='https://graph.facebook.com/v11.0/oauth/access_token',
	access_token_params=None,
	authorize_url='https://www.facebook.com/v11.0/dialog/oauth',
	authorize_params=None,
	api_base_url='https://graph.facebook.com/',
	client_kwargs={'scope': 'user:email'},
)

oauth.register(
	name='github',
	client_id='58877ba7ad9baef280b4',
	client_secret='',
	access_token_url='https://github.com/login/oauth/access_token',
	access_token_params=None,
	authorize_url='https://github.com/login/oauth/authorize',
	authorize_params=None,
	api_base_url='https://api.github.com/',
	client_kwargs={'scope': 'user:email'},
)

async def oauth_login(request):
	github = oauth.create_client('github')
	redirect_uri = request.url_for('oauth_authorize')
	return await github.authorize_redirect(request, redirect_uri)

async def oauth_authorize(request):
	github = oauth.create_client('github')
	token = await github.authorize_access_token(request)
	resp = await github.get('user', token=token)
	profile = resp.json()
	oauth_id = profile["id"]
	user_input = {
		"oauth_id" : oauth_id,
		"email" : profile["email"],
		"username" : profile["name"]
	}
	user = Identity.identity_oauth(oauth_id=oauth_id, input=user_input)
	token = await Authorize.authorize(user, device="pc", auto_delete=False)
	return PlainTextResponse(token)
