import requests

from settings import MAILGUN_API_KEY, MAILGUN_DOMAIN

api_url = "https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN
noreply = "discours.io <noreply@%s>" % MAILGUN_DOMAIN

tmplt = """<html><body>
    Follow the <a href='%s'>link</a> to authorize
    </body></html>
    """

baseUrl = "https://new.discours.io"


async def send_auth_email(user, token):
    try:
        to = "%s <%s>" % (user.username, user.email)
        url_with_token = "%s/confirm/%s" % (baseUrl, token)
        response = requests.post(
            api_url,
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": noreply,
                "to": to,
                "subject": "Confirm email",
                "html": tmplt % url_with_token,
            },
        )
        response.raise_for_status()
    except Exception as e:
        print(e)
