# OAuth Deployment Checklist

## 🚀 Quick Setup Guide

### 1. Backend Implementation
```bash
# Добавьте в requirements.txt или poetry
redis>=4.0.0
httpx>=0.24.0
pydantic>=2.0.0
```

### 2. Environment Variables
```bash
# .env file
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
VK_APP_ID=your_vk_app_id
VK_APP_SECRET=your_vk_app_secret
YANDEX_CLIENT_ID=your_yandex_client_id
YANDEX_CLIENT_SECRET=your_yandex_client_secret

REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your_super_secret_jwt_key
JWT_EXPIRATION_HOURS=24
```

### 3. Database Migration
```sql
-- Create oauth_links table
CREATE TABLE oauth_links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    provider_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(provider, provider_id)
);

CREATE INDEX idx_oauth_links_user_id ON oauth_links(user_id);
CREATE INDEX idx_oauth_links_provider ON oauth_links(provider, provider_id);
```

### 4. OAuth Provider Setup

#### Google OAuth
1. Перейти в [Google Cloud Console](https://console.cloud.google.com/)
2. Создать новый проект или выбрать существующий
3. Включить Google+ API
4. Настроить OAuth consent screen
5. Создать OAuth 2.0 credentials
6. Добавить redirect URIs:
   - `https://your-domain.com/auth/oauth/google/callback`
   - `http://localhost:3000/auth/oauth/google/callback` (для разработки)

#### Facebook OAuth
1. Перейти в [Facebook Developers](https://developers.facebook.com/)
2. Создать новое приложение
3. Добавить продукт "Facebook Login"
4. Настроить Valid OAuth Redirect URIs:
   - `https://your-domain.com/auth/oauth/facebook/callback`

#### GitHub OAuth
1. Перейти в [GitHub Settings](https://github.com/settings/applications/new)
2. Создать новое OAuth App
3. Настроить Authorization callback URL:
   - `https://your-domain.com/auth/oauth/github/callback`

### 5. Backend Endpoints (FastAPI example)
```python
# auth/oauth.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth/oauth")

@router.get("/{provider}")
async def oauth_redirect(provider: str, state: str, redirect_uri: str):
    # Валидация провайдера
    if provider not in ["google", "facebook", "github", "vk", "yandex"]:
        raise HTTPException(400, "Unsupported provider")
    
    # Сохранение state в Redis
    await store_oauth_state(state, redirect_uri)
    
    # Генерация URL провайдера
    oauth_url = generate_provider_url(provider, state, redirect_uri)
    
    return RedirectResponse(url=oauth_url)

@router.get("/{provider}/callback")
async def oauth_callback(provider: str, code: str, state: str):
    # Проверка state
    stored_data = await get_oauth_state(state)
    if not stored_data:
        raise HTTPException(400, "Invalid state")
    
    # Обмен code на user_data
    user_data = await exchange_code_for_user_data(provider, code)
    
    # Создание/поиск пользователя
    user = await get_or_create_user_from_oauth(provider, user_data)
    
    # Генерация JWT
    access_token = generate_jwt_token(user.id)
    
    # Редирект с токеном
    return RedirectResponse(
        url=f"{stored_data['redirect_uri']}?state={state}&access_token={access_token}"
    )
```

### 6. Testing
```bash
# Запуск E2E тестов
npm run test:e2e -- oauth.spec.ts

# Проверка OAuth endpoints
curl -X GET "http://localhost:8000/auth/oauth/google?state=test&redirect_uri=http://localhost:3000"
```

### 7. Production Deployment

#### Frontend
- [ ] Проверить корректность `coreApiUrl` в production
- [ ] Добавить обработку ошибок OAuth в UI
- [ ] Настроить CSP headers для OAuth редиректов

#### Backend
- [ ] Настроить HTTPS для всех OAuth endpoints
- [ ] Добавить rate limiting для OAuth endpoints
- [ ] Настроить CORS для фронтенд доменов
- [ ] Добавить мониторинг OAuth ошибок
- [ ] Настроить логирование OAuth событий

#### Infrastructure
- [ ] Настроить Redis для production
- [ ] Добавить health checks для OAuth endpoints
- [ ] Настроить backup для oauth_links таблицы

### 8. Security Checklist
- [ ] Все OAuth секреты в environment variables
- [ ] State validation с TTL (10 минут)
- [ ] CSRF protection включен
- [ ] Redirect URI validation
- [ ] Rate limiting на OAuth endpoints
- [ ] Логирование всех OAuth событий
- [ ] HTTPS обязателен в production

### 9. Monitoring
```python
# Добавить метрики для мониторинга
from prometheus_client import Counter, Histogram

oauth_requests = Counter('oauth_requests_total', 'OAuth requests', ['provider', 'status'])
oauth_duration = Histogram('oauth_duration_seconds', 'OAuth request duration')

@router.get("/{provider}")
async def oauth_redirect(provider: str, state: str, redirect_uri: str):
    with oauth_duration.time():
        try:
            # OAuth logic
            oauth_requests.labels(provider=provider, status='success').inc()
        except Exception as e:
            oauth_requests.labels(provider=provider, status='error').inc()
            raise
```

## 🔧 Troubleshooting

### Частые ошибки

1. **"OAuth state mismatch"**
   - Проверьте TTL Redis
   - Убедитесь, что state генерируется правильно

2. **"Provider authentication failed"**
   - Проверьте client_id и client_secret
   - Убедитесь, что redirect_uri совпадает с настройками провайдера

3. **"Invalid redirect URI"**
   - Добавьте все возможные redirect URIs в настройки приложения
   - Проверьте HTTPS/HTTP в production/development

### Логи для отладки
```bash
# Backend логи
tail -f /var/log/app/oauth.log | grep "oauth"

# Frontend логи (browser console)
# Фильтр: "[oauth]" или "[SessionProvider]"
``` 