# Система авторизации Discours.io

## Обзор архитектуры

Система авторизации построена на модульной архитектуре с разделением на независимые компоненты:

```
auth/
├── tokens/           # Система управления токенами
├── middleware.py     # HTTP middleware для аутентификации
├── decorators.py     # GraphQL декораторы авторизации
├── oauth.py          # OAuth провайдеры
├── orm.py           # ORM модели пользователей
├── permissions.py    # Система разрешений
├── identity.py       # Методы идентификации
├── jwtcodec.py      # JWT кодек
├── validations.py    # Валидация данных
├── credentials.py    # Работа с креденшалами
├── exceptions.py     # Исключения авторизации
└── handler.py        # HTTP обработчики
```

## Система токенов

### Система сессий

Система использует стандартный `SessionTokenManager` для управления сессиями в Redis:

**Принцип работы:**
1. При успешной аутентификации токен сохраняется в Redis через `SessionTokenManager`
2. Сессии автоматически проверяются при каждом запросе через `verify_session`
3. TTL сессий: 30 дней (настраивается)
4. Автоматическое обновление `last_activity` при активности

**Redis структура сессий:**
```
session:{user_id}:{token}     # hash с данными сессии
user_sessions:{user_id}       # set с активными токенами
```

**Логика получения токена (приоритет):**
1. `scope["auth_token"]` - токен из текущего запроса
2. Заголовок `Authorization`
3. Заголовок `SESSION_TOKEN_HEADER`
4. Cookie `SESSION_COOKIE_NAME`

### Типы токенов

| Тип | TTL | Назначение |
|-----|-----|------------|
| `session` | 30 дней | Токены пользовательских сессий |
| `verification` | 1 час | Токены подтверждения (email, телефон) |
| `oauth_access` | 1 час | OAuth access токены |
| `oauth_refresh` | 30 дней | OAuth refresh токены |

### Компоненты системы токенов

#### `SessionTokenManager`
Управление сессиями пользователей:
- JWT-токены с payload `{user_id, username, iat, exp}`
- Redis хранение для отзыва и управления
- Поддержка multiple sessions per user
- Автоматическое продление при активности

**Основные методы:**
```python
async def create_session(user_id: str, auth_data=None, username=None, device_info=None) -> str
async def verify_session(token: str) -> Optional[Any]
async def refresh_session(user_id: int, old_token: str, device_info=None) -> Optional[str]
async def revoke_session_token(token: str) -> bool
async def revoke_user_sessions(user_id: str) -> int
```

**Redis структура:**
```
session:{user_id}:{token}     # hash с данными сессии
user_sessions:{user_id}       # set с активными токенами
{user_id}-{username}-{token}  # legacy ключи для совместимости
```

#### `VerificationTokenManager`
Управление токенами подтверждения:
- Email verification
- Phone verification
- Password reset
- Одноразовые токены

**Основные методы:**
```python
async def create_verification_token(user_id: str, verification_type: str, data: TokenData, ttl=None) -> str
async def validate_verification_token(token: str) -> tuple[bool, Optional[TokenData]]
async def confirm_verification_token(token: str) -> Optional[TokenData]  # одноразовое использование
```

#### `OAuthTokenManager`
Управление OAuth токенами:
- Google, GitHub, Facebook, X, Telegram, VK, Yandex
- Access/refresh token pairs
- Provider-specific storage

**Redis структура:**
```
oauth_access:{user_id}:{provider}   # access токен
oauth_refresh:{user_id}:{provider}  # refresh токен
```

#### `BatchTokenOperations`
Пакетные операции для производительности:
- Массовая валидация токенов
- Пакетный отзыв
- Очистка истекших токенов

#### `TokenMonitoring`
Мониторинг и статистика:
- Подсчет активных токенов по типам
- Статистика использования памяти
- Health check системы токенов
- Оптимизация производительности

### TokenStorage (Фасад)
Упрощенный фасад для основных операций:
```python
# Основные методы
await TokenStorage.create_session(user_id, username=username)
await TokenStorage.verify_session(token)
await TokenStorage.refresh_session(user_id, old_token, device_info)
await TokenStorage.revoke_session(token)

# Deprecated методы (для миграции)
await TokenStorage.create_onetime(user)  # -> VerificationTokenManager
```

## OAuth система

### Поддерживаемые провайдеры
- **Google** - OpenID Connect
- **GitHub** - OAuth 2.0
- **Facebook** - Facebook Login
- **X (Twitter)** - OAuth 2.0 (без email)
- **Telegram** - Telegram Login Widget (без email)
- **VK** - VK OAuth (требует разрешений для email)
- **Yandex** - Yandex OAuth

### Процесс OAuth авторизации
1. **Инициация**: `GET /oauth/{provider}?state={csrf_token}&redirect_uri={url}`
2. **Callback**: `GET /oauth/{provider}/callback?code={code}&state={state}`
3. **Обработка**: Получение user profile, создание/обновление пользователя
4. **Результат**: JWT токен в cookie + redirect на фронтенд

### Безопасность OAuth
- **PKCE** (Proof Key for Code Exchange) для дополнительной безопасности
- **State параметры** хранятся в Redis с TTL 10 минут
- **Одноразовые сессии** - после использования удаляются
- **Генерация временных email** для провайдеров без email (X, Telegram)

## Middleware и декораторы

### AuthMiddleware
HTTP middleware для автоматической аутентификации:
- Извлечение токенов из cookies/headers
- Валидация JWT токенов
- Добавление user context в request
- Обработка истекших токенов

### GraphQL декораторы
```python
@auth_required          # Требует авторизации
@permission_required    # Требует конкретных разрешений
@admin_required        # Требует admin права
```

## ORM модели

### Author (Пользователь)
```python
class Author:
    id: int
    email: str
    name: str
    slug: str
    password: Optional[str]      # bcrypt hash
    pic: Optional[str]           # URL аватара
    bio: Optional[str]
    email_verified: bool
    created_at: int
    updated_at: int
    last_seen: int

    # OAuth связи
    oauth_accounts: List[OAuthAccount]
```

### OAuthAccount
```python
class OAuthAccount:
    id: int
    author_id: int
    provider: str               # google, github, etc.
    provider_id: str           # ID пользователя у провайдера
    provider_email: Optional[str]
    provider_data: dict        # Дополнительные данные от провайдера
```

## Система разрешений

### Роли
- **user** - Обычный пользователь
- **moderator** - Модератор контента
- **admin** - Администратор системы

### Разрешения
- **read** - Чтение контента
- **write** - Создание контента
- **moderate** - Модерация контента
- **admin** - Административные действия

### Проверка разрешений
```python
from auth.permissions import check_permission

@permission_required("moderate")
async def moderate_content(info, content_id: str):
    # Только пользователи с правами модерации
    pass
```

## Безопасность

### Хеширование паролей
- **bcrypt** с rounds=10
- **SHA256** препроцессинг для длинных паролей
- **Salt** автоматически генерируется bcrypt

### JWT токены
- **Алгоритм**: HS256
- **Secret**: Из переменной окружения JWT_SECRET
- **Payload**: `{user_id, username, iat, exp}`
- **Expiration**: 30 дней (настраивается)

### Redis security
- **TTL** для всех токенов
- **Атомарные операции** через pipelines
- **SCAN** вместо KEYS для производительности
- **Транзакции** для критических операций

## Конфигурация

### Переменные окружения
```bash
# JWT
JWT_SECRET=your_super_secret_key
JWT_EXPIRATION_HOURS=720  # 30 дней

# Redis
REDIS_URL=redis://localhost:6379/0

# OAuth провайдеры
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
# ... и т.д.

# Session cookies
SESSION_COOKIE_NAME=session_token
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
SESSION_COOKIE_MAX_AGE=2592000  # 30 дней

# Frontend
FRONTEND_URL=https://yourdomain.com
```

## API Endpoints

### Аутентификация
```
POST /auth/login           # Email/password вход
POST /auth/logout          # Выход (отзыв токена)
POST /auth/refresh         # Обновление токена
POST /auth/register        # Регистрация
```

### OAuth
```
GET  /oauth/{provider}            # Инициация OAuth
GET  /oauth/{provider}/callback   # OAuth callback
```

### Профиль
```
GET  /auth/profile         # Текущий пользователь
PUT  /auth/profile         # Обновление профиля
POST /auth/change-password # Смена пароля
```

## Мониторинг и логирование

### Метрики
- Количество активных сессий по типам
- Использование памяти Redis
- Статистика OAuth провайдеров
- Health check всех компонентов

### Логирование
- **INFO**: Успешные операции (создание сессий, OAuth)
- **WARNING**: Подозрительная активность (неверные пароли)
- **ERROR**: Ошибки системы (Redis недоступен, JWT invalid)

## Производительность

### Оптимизации Redis
- **Pipeline операции** для атомарности
- **Batch обработка** токенов (100-1000 за раз)
- **SCAN** вместо KEYS для безопасности
- **TTL** автоматическая очистка

### Кэширование
- **@lru_cache** для часто используемых ключей
- **Connection pooling** для Redis
- **JWT decode caching** в middleware

## Миграция и совместимость

### Legacy поддержка
- Старые ключи Redis: `{user_id}-{username}-{token}`
- Автоматическая миграция при обращении
- Deprecated методы с предупреждениями

### Планы развития
- [ ] Удаление legacy ключей
- [ ] Переход на RS256 для JWT
- [ ] WebAuthn/FIDO2 поддержка
- [ ] Rate limiting для auth endpoints
- [ ] Audit log для всех auth операций

## Тестирование

### Unit тесты
```bash
pytest tests/auth/          # Все auth тесты
pytest tests/auth/test_oauth.py  # OAuth тесты
pytest tests/auth/test_tokens.py # Token тесты
```

### Integration тесты
- OAuth flow с моками провайдеров
- Redis операции
- JWT lifecycle
- Permission checks

## Troubleshooting

### Частые проблемы
1. **Redis connection failed** - Проверить REDIS_URL и доступность
2. **JWT invalid** - Проверить JWT_SECRET и время сервера
3. **OAuth failed** - Проверить client_id/secret провайдеров
4. **Session not found** - Возможно токен истек или отозван

### Диагностика
```python
# Проверка health системы токенов
from auth.tokens.monitoring import TokenMonitoring
health = await TokenMonitoring().health_check()

# Статистика токенов
stats = await TokenMonitoring().get_token_statistics()
```
