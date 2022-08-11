import requests
from starlette.responses import RedirectResponse
from auth.authenticate import EmailAuthenticate, ResetPassword
from base.orm import local_session
from settings import BACKEND_URL, MAILGUN_API_KEY, MAILGUN_DOMAIN, RESET_PWD_URL, \
	CONFIRM_EMAIL_URL, ERROR_URL_ON_FRONTEND

MAILGUN_API_URL = "https://api.mailgun.net/v3/%s/messages" % (MAILGUN_DOMAIN)
MAILGUN_FROM = "postmaster <postmaster@%s>" % (MAILGUN_DOMAIN)

AUTH_URL = "%s/email_authorize" % (BACKEND_URL)

email_templates = {"confirm_email" : "", "auth_email" : "", "reset_password_email" : ""}

def load_email_templates():
	for name in email_templates:
		filename = "templates/%s.tmpl" % name
		with open(filename) as f:
			email_templates[name] = f.read()
	print("[auth.email] templates loaded")

async def send_confirm_email(user):
	text = email_templates["confirm_email"]
	token = await EmailAuthenticate.get_email_token(user)
	await send_email(user, AUTH_URL, text, token)

async def send_auth_email(user):
	text = email_templates["auth_email"]
	token = await EmailAuthenticate.get_email_token(user)
	await send_email(user, AUTH_URL, text, token)

async def send_reset_password_email(user):
	text = email_templates["reset_password_email"]
	token = await ResetPassword.get_reset_token(user)
	await send_email(user, RESET_PWD_URL, text, token)

async def send_email(user, url, text, token):
	to = "%s <%s>" % (user.username, user.email)
	url_with_token = "%s?token=%s" % (url, token)
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
		url_with_error = "%s?error=%s" % (ERROR_URL_ON_FRONTEND, "INVALID_TOKEN")
		return RedirectResponse(url = url_with_error)

	try:
		auth_token, user = await EmailAuthenticate.authenticate(token)
	except:
		url_with_error = "%s?error=%s" % (ERROR_URL_ON_FRONTEND, "INVALID_TOKEN")
		return RedirectResponse(url = url_with_error)
	
	if not user.emailConfirmed:
		with local_session() as session:
			user.emailConfirmed = True
			session.commit()

	response = RedirectResponse(url = CONFIRM_EMAIL_URL)
	response.set_cookie("token", auth_token)
	return response
