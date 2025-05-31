 # OAuth Implementation Guide

## Фронтенд (Текущая реализация)

### Контекст сессии
```typescript
// src/context/session.tsx
const oauth = (provider: string) => {
  console.info('[oauth] Starting OAuth flow for provider:', provider)
  
  if (isServer) {
    console.warn('[oauth] OAuth not available during SSR')
    return
  }

  // Генерируем state для OAuth
  const state = crypto.randomUUID()
  localStorage.setItem('oauth_state', state)
  
  // Формируем URL для OAuth
  const oauthUrl = `${coreApiUrl}/auth/oauth/${provider}?state=${state}&redirect_uri=${encodeURIComponent(window.location.origin)}`
  
  // Перенаправляем на OAuth провайдера
  window.location.href = oauthUrl
}
```

### Обработка OAuth callback
```typescript
// Обработка OAuth параметров в SessionProvider
createEffect(
  on([() => searchParams?.state, () => searchParams?.access_token, () => searchParams?.token], 
    ([state, access_token, token]) => {
      // OAuth обработка
      if (state && access_token) {
        console.info('[SessionProvider] Processing OAuth callback')
        const storedState = !isServer ? localStorage.getItem('oauth_state') : null

        if (storedState === state) {
          console.info('[SessionProvider] OAuth state verified')
          batch(() => {
            changeSearchParams({ mode: 'confirm-email', m: 'auth', access_token }, { replace: true })
            if (!isServer) localStorage.removeItem('oauth_state')
          })
        } else {
          console.warn('[SessionProvider] OAuth state mismatch')
          setAuthError('OAuth state mismatch')
        }
        return
      }

      // Обработка токена сброса пароля
      if (token) {
        console.info('[SessionProvider] Processing password reset token')
        changeSearchParams({ mode: 'change-password', m: 'auth', token }, { replace: true })
      }
    }, 
    { defer: true }
  )
)
```

## Бекенд Requirements

### 1. OAuth Endpoints

#### GET `/auth/oauth/{provider}`
```python
@router.get("/auth/oauth/{provider}")
async def oauth_redirect(
    provider: str,
    state: str,
    redirect_uri: str,
    request: Request
):
    """
    Инициация OAuth flow с внешним провайдером
    
    Args:
        provider: Провайдер OAuth (google, facebook, github)
        state: CSRF токен от клиента
        redirect_uri: URL для редиректа после авторизации
    
    Returns:
        RedirectResponse: Редирект на провайдера OAuth
    """
    
    # Валидация провайдера
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported OAuth provider")
    
    # Сохранение state в сессии/Redis для проверки
    await store_oauth_state(state, redirect_uri)
    
    # Генерация URL провайдера
    oauth_url = generate_provider_url(provider, state, redirect_uri)
    
    return RedirectResponse(url=oauth_url)
```

#### GET `/auth/oauth/{provider}/callback`
```python
@router.get("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    request: Request
):
    """
    Обработка callback от OAuth провайдера
    
    Args:
        provider: Провайдер OAuth
        code: Authorization code от провайдера
        state: CSRF токен для проверки
    
    Returns:
        RedirectResponse: Редирект обратно на фронтенд с токеном
    """
    
    # Проверка state
    stored_data = await get_oauth_state(state)
    if not stored_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    
    # Обмен code на access_token
    try:
        user_data = await exchange_code_for_user_data(provider, code)
    except OAuthException as e:
        logger.error(f"OAuth error for {provider}: {e}")
        return RedirectResponse(url=f"{stored_data['redirect_uri']}?error=oauth_failed")
    
    # Поиск/создание пользователя
    user = await get_or_create_user_from_oauth(provider, user_data)
    
    # Генерация JWT токена
    access_token = generate_jwt_token(user.id)
    
    # Редирект обратно на фронтенд
    redirect_url = f"{stored_data['redirect_uri']}?state={state}&access_token={access_token}"
    return RedirectResponse(url=redirect_url)
```

### 2. Provider Configuration

#### Google OAuth
```python
GOOGLE_OAUTH_CONFIG = {
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "user_info_url": "https://www.googleapis.com/oauth2/v2/userinfo",
    "scope": "openid email profile"
}
```

#### Facebook OAuth
```python
FACEBOOK_OAUTH_CONFIG = {
    "client_id": os.getenv("FACEBOOK_APP_ID"),
    "client_secret": os.getenv("FACEBOOK_APP_SECRET"),
    "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
    "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
    "user_info_url": "https://graph.facebook.com/v18.0/me",
    "scope": "email public_profile"
}
```

#### GitHub OAuth
```python
GITHUB_OAUTH_CONFIG = {
    "client_id": os.getenv("GITHUB_CLIENT_ID"),
    "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
    "auth_url": "https://github.com/login/oauth/authorize",
    "token_url": "https://github.com/login/oauth/access_token",
    "user_info_url": "https://api.github.com/user",
    "scope": "read:user user:email"
}
```

### 3. User Management

#### OAuth User Model
```python
class OAuthUser(BaseModel):
    provider: str
    provider_id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    raw_data: dict
```

#### User Creation/Linking
```python
async def get_or_create_user_from_oauth(
    provider: str, 
    oauth_data: OAuthUser
) -> User:
    """
    Поиск существующего пользователя или создание нового
    
    Args:
        provider: OAuth провайдер
        oauth_data: Данные пользователя от провайдера
    
    Returns:
        User: Пользователь в системе
    """
    
    # Поиск по OAuth связке
    oauth_link = await OAuthLink.get_by_provider_and_id(
        provider=provider,
        provider_id=oauth_data.provider_id
    )
    
    if oauth_link:
        return await User.get(oauth_link.user_id)
    
    # Поиск по email
    existing_user = await User.get_by_email(oauth_data.email)
    
    if existing_user:
        # Привязка OAuth к существующему пользователю
        await OAuthLink.create(
            user_id=existing_user.id,
            provider=provider,
            provider_id=oauth_data.provider_id,
            provider_data=oauth_data.raw_data
        )
        return existing_user
    
    # Создание нового пользователя
    new_user = await User.create(
        email=oauth_data.email,
        name=oauth_data.name,
        pic=oauth_data.avatar_url,
        is_verified=True,  # OAuth email считается верифицированным
        registration_method='oauth',
        registration_provider=provider
    )
    
    # Создание OAuth связки
    await OAuthLink.create(
        user_id=new_user.id,
        provider=provider,
        provider_id=oauth_data.provider_id,
        provider_data=oauth_data.raw_data
    )
    
    return new_user
```

### 4. Security

#### State Management
```python
import redis
from datetime import timedelta

redis_client = redis.Redis()

async def store_oauth_state(
    state: str, 
    redirect_uri: str, 
    ttl: timedelta = timedelta(minutes=10)
):
    """Сохранение OAuth state с TTL"""
    key = f"oauth_state:{state}"
    data = {
        "redirect_uri": redirect_uri,
        "created_at": datetime.utcnow().isoformat()
    }
    await redis_client.setex(key, ttl, json.dumps(data))

async def get_oauth_state(state: str) -> Optional[dict]:
    """Получение и удаление OAuth state"""
    key = f"oauth_state:{state}"
    data = await redis_client.get(key)
    if data:
        await redis_client.delete(key)  # One-time use
        return json.loads(data)
    return None
```

#### CSRF Protection
```python
def validate_oauth_state(stored_state: str, received_state: str) -> bool:
    """Проверка OAuth state для защиты от CSRF"""
    return stored_state == received_state

def validate_redirect_uri(uri: str) -> bool:
    """Валидация redirect_uri для предотвращения открытых редиректов"""
    allowed_domains = [
        "localhost:3000",
        "discours.io",
        "new.discours.io"
    ]
    
    parsed = urlparse(uri)
    return any(domain in parsed.netloc for domain in allowed_domains)
```

### 5. Database Schema

#### OAuth Links Table
```sql
CREATE TABLE oauth_links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    provider_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(provider, provider_id),
    INDEX(user_id),
    INDEX(provider, provider_id)
);
```

### 6. Environment Variables

#### Required Config
```bash
# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Facebook OAuth  
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Redis для state management
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET=your_jwt_secret_key
JWT_EXPIRATION_HOURS=24
```

### 7. Error Handling

#### OAuth Exceptions
```python
class OAuthException(Exception):
    pass

class InvalidProviderException(OAuthException):
    pass

class StateValidationException(OAuthException):
    pass

class ProviderAPIException(OAuthException):
    pass

# Error responses
@app.exception_handler(OAuthException)
async def oauth_exception_handler(request: Request, exc: OAuthException):
    logger.error(f"OAuth error: {exc}")
    return RedirectResponse(
        url=f"{request.base_url}?error=oauth_failed&message={str(exc)}"
    )
```

### 8. Testing

#### Unit Tests
```python
def test_oauth_redirect():
    response = client.get("/auth/oauth/google?state=test&redirect_uri=http://localhost:3000")
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]

def test_oauth_callback():
    # Mock provider response
    with mock.patch('oauth.exchange_code_for_user_data') as mock_exchange:
        mock_exchange.return_value = OAuthUser(
            provider="google",
            provider_id="123456",
            email="test@example.com",
            name="Test User"
        )
        
        response = client.get("/auth/oauth/google/callback?code=test_code&state=test_state")
        assert response.status_code == 307
        assert "access_token=" in response.headers["location"]
```

## Frontend Testing

### E2E Tests
```typescript
// tests/oauth.spec.ts
test('OAuth flow with Google', async ({ page }) => {
  await page.goto('/login')
  
  // Click Google OAuth button
  await page.click('[data-testid="oauth-google"]')
  
  // Should redirect to Google
  await page.waitForURL(/accounts\.google\.com/)
  
  // Mock successful OAuth (in test environment)
  await page.goto('/?state=test&access_token=mock_token')
  
  // Should be logged in
  await expect(page.locator('[data-testid="user-menu"]')).toBeVisible()
})
```

## Deployment Checklist

- [ ] Зарегистрировать OAuth приложения у провайдеров
- [ ] Настроить redirect URLs в консолях провайдеров
- [ ] Добавить environment variables
- [ ] Настроить Redis для state management
- [ ] Создать таблицу oauth_links
- [ ] Добавить rate limiting для OAuth endpoints
- [ ] Настроить мониторинг OAuth ошибок
- [ ] Протестировать все провайдеры в staging
- [ ] Добавить логирование OAuth событий