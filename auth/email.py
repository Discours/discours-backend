from typing import Any

import requests

from settings import MAILGUN_API_KEY, MAILGUN_DOMAIN

api_url = "https://api.mailgun.net/v3/%s/messages" % (MAILGUN_DOMAIN or "discours.io")
noreply = "discours.io <noreply@%s>" % (MAILGUN_DOMAIN or "discours.io")
lang_subject = {"ru": "Подтверждение почты", "en": "Confirm email"}


async def send_auth_email(user: Any, token: str, lang: str = "ru", template: str = "email_confirmation") -> None:
    try:
        to = f"{user.name} <{user.email}>"
        if lang not in ["ru", "en"]:
            lang = "ru"
        subject = lang_subject.get(lang, lang_subject["en"])
        template = template + "_" + lang
        payload = {
            "from": noreply,
            "to": to,
            "subject": subject,
            "template": template,
            "h:X-Mailgun-Variables": f'{{ "token": "{token}" }}',
        }
        print(f"[auth.email] payload: {payload!r}")
        # debug
        # print('http://localhost:3000/?modal=auth&mode=confirm-email&token=%s' % token)
        response = requests.post(api_url, auth=("api", MAILGUN_API_KEY), data=payload, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(e)
