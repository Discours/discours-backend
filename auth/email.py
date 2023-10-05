import httpx
from settings import MAILGUN_API_KEY, MAILGUN_DOMAIN

api_url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN or 'discours.io'}/messages"
noreply = f"discours.io <noreply@{MAILGUN_DOMAIN or 'discours.io'}>"
lang_subject = {"ru": "Подтверждение почты", "en": "Confirm email"}

async def send_auth_email(user, token, lang="ru", template="email_confirmation"):
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
        print(f"[auth.email] payload: {payload}")
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, auth=("api", MAILGUN_API_KEY), data=payload)
            response.raise_for_status()
    except Exception as e:
        print(e)
