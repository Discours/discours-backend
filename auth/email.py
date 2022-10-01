import requests

from settings import BACKEND_URL, MAILGUN_API_KEY, MAILGUN_DOMAIN

MAILGUN_API_URL = "https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN
MAILGUN_FROM = "discours.io <noreply@%s>" % MAILGUN_DOMAIN


async def send_auth_email(user, token):
    text = """<html><body>
    Follow the <a href='%s'>link</link> to authorize
    </body></html>
    """
    url = "%s/confirm-email" % BACKEND_URL
    to = "%s <%s>" % (user.username, user.email)
    url_with_token = "%s?token=%s" % (url, token)
    text = text % url_with_token
    response = requests.post(
        MAILGUN_API_URL,
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": MAILGUN_FROM,
            "to": to,
            "subject": "Confirm email",
            "html": text,
        },
    )
    response.raise_for_status()
