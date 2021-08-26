from authlib.integrations.starlette_client import OAuth
from starlette.responses import PlainTextResponse

from auth.authorize import Authorize
from auth.identity import Identity

from settings import OAUTH_CLIENTS

oauth = OAuth()

oauth.register(
	name='facebook',
	client_id=OAUTH_CLIENTS["FACEBOOK"]["id"],
	client_secret=OAUTH_CLIENTS["FACEBOOK"]["key"],
	access_token_url='https://graph.facebook.com/v11.0/oauth/access_token',
	access_token_params=None,
	authorize_url='https://www.facebook.com/v11.0/dialog/oauth',
	authorize_params=None,
	api_base_url='https://graph.facebook.com/',
	client_kwargs={'scope': 'public_profile email'},
)

oauth.register(
	name='github',
	client_id=OAUTH_CLIENTS["GITHUB"]["id"],
	client_secret=OAUTH_CLIENTS["GITHUB"]["key"],
	access_token_url='https://github.com/login/oauth/access_token',
	access_token_params=None,
	authorize_url='https://github.com/login/oauth/authorize',
	authorize_params=None,
	api_base_url='https://api.github.com/',
	client_kwargs={'scope': 'user:email'},
)

oauth.register(
	name='google',
	client_id=OAUTH_CLIENTS["GOOGLE"]["id"],
	client_secret=OAUTH_CLIENTS["GOOGLE"]["key"],
	server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
	client_kwargs={'scope': 'openid email profile'}
)

async def google_profile(client, request, token):
	profile = await client.parse_id_token(request, token)
	profile["id"] = profile["sub"]
	return profile

async def facebook_profile(client, request, token):
	profile = await client.get('me?fields=name,id,email', token=token)
	return profile.json()

async def github_profile(client, request, token):
	profile = await client.get('user', token=token)
	return profile.json()

profile_callbacks = {
	"google" : google_profile,
	"facebook" : facebook_profile,
	"github" : github_profile
}


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
	get_profile = profile_callbacks[provider]
	profile = await get_profile(client, request, token)
	user_oauth_info = "%s:%s" % (provider, profile["id"])
	user_input = {
		"oauth" : user_oauth_info,
		"email" : profile["email"],
		"username" : profile["name"]
	}
	user = Identity.identity_oauth(user_input)
	token = await Authorize.authorize(user, device="pc")
	return PlainTextResponse(token)
