import requests
from starlette.responses import PlainTextResponse
from starlette.exceptions import HTTPException

from auth.authenticate import EmailAuthenticate, ResetPassword

from settings import BACKEND_URL, MAILGUN_API_KEY, MAILGUN_DOMAIN, RESET_PWD_URL

MAILGUN_API_URL = "https://api.mailgun.net/v3/%s/messages" % (MAILGUN_DOMAIN)
MAILGUN_FROM = "postmaster <postmaster@%s>" % (MAILGUN_DOMAIN)

AUTH_URL = "%s/email_authorize" % (BACKEND_URL)

async def send_confirm_email(user):
	text = "<html><body>To confirm registration follow the <a href='%s'>link</link></body></html>"
	token = await EmailAuthenticate.get_email_token(user)
	await send_email(user, AUTH_URL, text, token)

async def send_auth_email(user):
	text = "<html><body>To enter the site follow the <a href='%s'>link</link></body></html>"
	token = await EmailAuthenticate.get_email_token(user)
	await send_email(user, AUTH_URL, text, token)

async def send_reset_password_email(user):
	text = "<html><body>To reset password follow the <a href='%s'>link</link></body></html>"
	token = await ResetPassword.get_reset_token(user)
	await send_email(user, RESET_PWD_URL, text, token)

async def send_email(user, url, text, token):
	to = "%s <%s>" % (user.username, user.email)
	url_with_token = "%s/%s" % (url, token)
	text = text % (url_with_token)
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
