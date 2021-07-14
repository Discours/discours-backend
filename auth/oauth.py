from authlib.integrations.starlette_client import OAuth
from starlette.responses import PlainTextResponse

from auth.authorize import Authorize
from auth.identity import Identity

from sensitive_settings import CLIENT_ID, CLIENT_SECRET

oauth = OAuth()

oauth.register(
	name='facebook',
	client_id=CLIENT_ID["FACEBOOK"],
	client_secret=CLIENT_SECRET["FACEBOOK"],
	access_token_url='https://graph.facebook.com/v11.0/oauth/access_token',
	access_token_params=None,
	authorize_url='https://www.facebook.com/v11.0/dialog/oauth',
	authorize_params=None,
	api_base_url='https://graph.facebook.com/',
	client_kwargs={'scope': 'user:email'},
)

oauth.register(
	name='github',
	client_id=CLIENT_ID["GITHUB"],
	client_secret=CLIENT_SECRET["GITHUB"],
	access_token_url='https://github.com/login/oauth/access_token',
	access_token_params=None,
	authorize_url='https://github.com/login/oauth/authorize',
	authorize_params=None,
	api_base_url='https://api.github.com/',
	client_kwargs={'scope': 'user:email'},
)

oauth.register(
	name='google',
	client_id=CLIENT_ID["GOOGLE"],
	client_secret=CLIENT_SECRET["GOOGLE"],
	access_token_url='https://oauth2.googleapis.com/token',
	access_token_params=None,
	authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
	authorize_params=None,
	api_base_url='https://oauth2.googleapis.com/',
	client_kwargs={'scope': 'openid email profile'}
)

async def oauth_login(request):
	provider = request.path_params['provider']
	request.session['provider'] = provider
	client = oauth.create_client(provider)
	redirect_uri = request.url_for('oauth_authorize')
	return await client.authorize_redirect(request, redirect_uri)

async def oauth_authorize(request):
	provider = request.session['provider']
	client = oauth.create_client(provider)
	token = await client.authorize_access_token(request)
	resp = await client.get('user', token=token)
	profile = resp.json()
	oauth_id = profile["id"]
	user_input = {
		"oauth_id" : oauth_id,
		"email" : profile["email"],
		"username" : profile["name"]
	}
	user = Identity.identity_oauth(user_input)
	token = await Authorize.authorize(user, device="pc", auto_delete=False)
	return PlainTextResponse(token)
