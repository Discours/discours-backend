# OAuth Providers Setup Guide

This guide explains how to set up OAuth authentication for various social platforms.

## Supported Providers

The platform supports the following OAuth providers:
- Google
- GitHub
- Facebook
- X (Twitter)
- Telegram
- VK (VKontakte)
- Yandex

## Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Google OAuth
OAUTH_CLIENTS_GOOGLE_ID=your_google_client_id
OAUTH_CLIENTS_GOOGLE_KEY=your_google_client_secret

# GitHub OAuth
OAUTH_CLIENTS_GITHUB_ID=your_github_client_id
OAUTH_CLIENTS_GITHUB_KEY=your_github_client_secret

# Facebook OAuth
OAUTH_CLIENTS_FACEBOOK_ID=your_facebook_app_id
OAUTH_CLIENTS_FACEBOOK_KEY=your_facebook_app_secret

# X (Twitter) OAuth
OAUTH_CLIENTS_X_ID=your_x_client_id
OAUTH_CLIENTS_X_KEY=your_x_client_secret

# Telegram OAuth
OAUTH_CLIENTS_TELEGRAM_ID=your_telegram_bot_token
OAUTH_CLIENTS_TELEGRAM_KEY=your_telegram_bot_secret

# VK OAuth
OAUTH_CLIENTS_VK_ID=your_vk_app_id
OAUTH_CLIENTS_VK_KEY=your_vk_secure_key

# Yandex OAuth
OAUTH_CLIENTS_YANDEX_ID=your_yandex_client_id
OAUTH_CLIENTS_YANDEX_KEY=your_yandex_client_secret
```

## Provider Setup Instructions

### Google
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API and OAuth 2.0
4. Create OAuth 2.0 Client ID credentials
5. Add your callback URLs: `https://yourdomain.com/oauth/google/callback`

### GitHub
1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Create a new OAuth App
3. Set Authorization callback URL: `https://yourdomain.com/oauth/github/callback`

### Facebook
1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Create a new app
3. Add Facebook Login product
4. Configure Valid OAuth redirect URIs: `https://yourdomain.com/oauth/facebook/callback`

### X (Twitter)
1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app
3. Enable OAuth 2.0 authentication
4. Set Callback URLs: `https://yourdomain.com/oauth/x/callback`
5. **Note**: X doesn't provide email addresses through their API

### Telegram
1. Create a bot with [@BotFather](https://t.me/botfather)
2. Use `/newbot` command and follow instructions
3. Get your bot token
4. Configure domain settings with `/setdomain` command
5. **Note**: Telegram doesn't provide email addresses

### VK (VKontakte)
1. Go to [VK for Developers](https://vk.com/dev)
2. Create a new application
3. Set Authorized redirect URI: `https://yourdomain.com/oauth/vk/callback`
4. **Note**: Email access requires special permissions from VK

### Yandex
1. Go to [Yandex OAuth](https://oauth.yandex.com/)
2. Create a new application
3. Set Callback URI: `https://yourdomain.com/oauth/yandex/callback`
4. Select required permissions: `login:email login:info`

## Email Handling

Some providers (X, Telegram) don't provide email addresses. In these cases:
- A temporary email is generated: `{provider}_{user_id}@oauth.local`
- Users can update their email in profile settings later
- `email_verified` is set to `false` for generated emails

## Usage in Frontend

OAuth URLs:
```
/oauth/google
/oauth/github
/oauth/facebook
/oauth/x
/oauth/telegram
/oauth/vk
/oauth/yandex
```

Each provider accepts a `state` parameter for CSRF protection and a `redirect_uri` for post-authentication redirects.

## Security Notes

- All OAuth flows use PKCE (Proof Key for Code Exchange) for additional security
- State parameters are stored in Redis with 10-minute TTL
- OAuth sessions are one-time use only
- Failed authentications are logged for monitoring
