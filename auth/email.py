import requests

from settings import MAILGUN_API_KEY, MAILGUN_DOMAIN

api_url = "https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN
noreply = "discours.io <noreply@%s>" % MAILGUN_DOMAIN


async def send_auth_email(user, token, lang="ru"):
    try:
        to = "%s <%s>" % (user.name, user.email)
        subject = "Confirm email"
        if lang not in ['ru', 'en']:
            lang = 'ru'
        template = "email_confirmation_" + lang

        response = requests.post(
            api_url,
            auth=("api", MAILGUN_API_KEY),
            data={"from": noreply,
                  "to": to,
                  "subject": subject,
                  "template": template,
                  "h:X-Mailgun-Variables": "{ \"token\": \"%s\" }" % token}
        )
        response.raise_for_status()
    except Exception as e:
        print(e)
