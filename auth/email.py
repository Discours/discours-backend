import requests
from starlette.responses import PlainTextResponse
from starlette.exceptions import HTTPException

from auth.authenticate import EmailAuthenticate

from settings import BACKEND_URL, MAILGUN_API_KEY, MAILGUN_DOMAIN

MAILGUN_API_URL = "https://api.mailgun.net/v3/%s/messages" % (MAILGUN_DOMAIN)
MAILGUN_FROM = "postmaster <postmaster@%s>" % (MAILGUN_DOMAIN)

AUTH_URL = "%s/email_authorize" % (BACKEND_URL)

async def send_confirm_email(user):
	text = "<html><body>To confirm registration follow the <a href='%s'>link</link></body></html>"
	await send_email(user, text)

async def send_auth_email(user):
	text = "<html><body>To enter the site follow the <a href='%s'>link</link></body></html>"
	await send_email(user, text)

async def send_email(user, text):
	token = await EmailAuthenticate.get_email_token(user)

	to = "%s <%s>" % (user.username, user.email)
	auth_url_with_token = "%s/%s" % (AUTH_URL, token)
	text = text % (auth_url_with_token)
	response = requests.post(
		MAILGUN_API_URL,
		auth = ("api", MAILGUN_API_KEY),
		data = {
			"from": MAILGUN_FROM,
			"to": to,
			"subject": "authorize log in",
			"html": text
			}
		)
	response.raise_for_status()

async def email_authorize(request):
	token = request.query_params.get('token')
	if not token:
		raise HTTPException(500, "invalid url")
	auth_token, user = await EmailAuthenticate.authenticate(token)
	return PlainTextResponse(auth_token)
