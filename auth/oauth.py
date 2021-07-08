from authlib.integrations.starlette_client import OAuth
from starlette.responses import PlainTextResponse

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

async def oauth_login(request):
    facebook = oauth.create_client('facebook')
    redirect_uri = request.url_for('oauth_authorize')
    return await facebook.authorize_redirect(request, redirect_uri)

async def oauth_authorize(request):
    facebook = oauth.create_client('facebook')
    token = await facebook.authorize_access_token(request)
    email = await facebook.parse_id_token(request, token)
    print(email)
    return PlainTextResponse("%s auth" % email)
