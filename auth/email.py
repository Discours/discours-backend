import requests

from auth.authenticate import EmailAuthenticate

from settings import MAILGUN_API_KEY, MAILGUN_DOMAIN

MAILGUN_API_URL = "https://api.mailgun.net/v3/%s/messages" % (MAILGUN_DOMAIN)
MAILGUN_FROM = "postmaster <postmaster@%s>" % (MAILGUN_DOMAIN)

AUTH_URL = "https://localhost:8080/auth"

async def send_auth_email(user):
	token = await EmailAuthenticate.get_email_token(user)

	to = "%s <%s>" % (user.username, user.email)
	text = "%s&token=%s" % (AUTH_URL, token)
	response = requests.post(
		MAILGUN_API_URL,
		auth = ("api", MAILGUN_API_KEY),
		data = {
			"from": MAILGUN_FROM,
			"to": to,
			"subject": "authorize log in",
			"text": text
			}
		)
	response.raise_for_status()
