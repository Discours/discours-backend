# OAuth Token Management

## Overview
Система управления OAuth токенами с использованием Redis для безопасного и производительного хранения токенов доступа и обновления от различных провайдеров.

## Архитектура

### Redis Storage
OAuth токены хранятся в Redis с автоматическим истечением (TTL):
- `oauth_access:{user_id}:{provider}` - access tokens
- `oauth_refresh:{user_id}:{provider}` - refresh tokens

### Поддерживаемые провайдеры
- Google OAuth 2.0
- Facebook Login
- GitHub OAuth

## API Documentation

### OAuthTokenStorage Class

#### store_access_token()
Сохраняет access token в Redis с автоматическим TTL.

```python
await OAuthTokenStorage.store_access_token(
    user_id=123,
    provider="google",
    access_token="ya29.a0AfH6SM...",
    expires_in=3600,
    additional_data={"scope": "profile email"}
)
```

#### store_refresh_token()
Сохраняет refresh token с длительным TTL (30 дней по умолчанию).

```python
await OAuthTokenStorage.store_refresh_token(
    user_id=123,
    provider="google",
    refresh_token="1//04...",
    ttl=2592000  # 30 дней
)
```

#### get_access_token()
Получает действующий access token из Redis.

```python
token_data = await OAuthTokenStorage.get_access_token(123, "google")
if token_data:
    access_token = token_data["token"]
    expires_in = token_data["expires_in"]
```

#### refresh_access_token()
Обновляет access token (и опционально refresh token).

```python
success = await OAuthTokenStorage.refresh_access_token(
    user_id=123,
    provider="google",
    new_access_token="ya29.new_token...",
    expires_in=3600,
    new_refresh_token="1//04new..."  # опционально
)
```

#### delete_tokens()
Удаляет все токены пользователя для провайдера.

```python
await OAuthTokenStorage.delete_tokens(123, "google")
```

#### get_user_providers()
Получает список OAuth провайдеров для пользователя.

```python
providers = await OAuthTokenStorage.get_user_providers(123)
# ["google", "github"]
```

#### extend_token_ttl()
Продлевает срок действия токена.

```python
# Продлить access token на 30 минут
success = await OAuthTokenStorage.extend_token_ttl(123, "google", "access", 1800)

# Продлить refresh token на 7 дней
success = await OAuthTokenStorage.extend_token_ttl(123, "google", "refresh", 604800)
```

#### get_token_info()
Получает подробную информацию о токенах включая TTL.

```python
info = await OAuthTokenStorage.get_token_info(123, "google")
# {
#   "user_id": 123,
#   "provider": "google",
#   "access_token": {"exists": True, "ttl": 3245},
#   "refresh_token": {"exists": True, "ttl": 2589600}
# }
```

## Data Structures

### Access Token Structure
```json
{
  "token": "ya29.a0AfH6SM...",
  "provider": "google",
  "user_id": 123,
  "created_at": 1640995200,
  "expires_in": 3600,
  "scope": "profile email",
  "token_type": "Bearer"
}
```

### Refresh Token Structure
```json
{
  "token": "1//04...",
  "provider": "google",
  "user_id": 123,
  "created_at": 1640995200
}
```

## Security Considerations

### Token Expiration
- **Access tokens**: TTL основан на `expires_in` от провайдера (обычно 1 час)
- **Refresh tokens**: TTL 30 дней по умолчанию
- **Автоматическая очистка**: Redis автоматически удаляет истекшие токены
- **Внутренняя система истечения**: Использует SET + EXPIRE для точного контроля TTL

### Redis Expiration Benefits
- **Гибкость**: Можно изменять TTL существующих токенов через EXPIRE
- **Мониторинг**: Команда TTL показывает оставшееся время жизни токена
- **Расширение**: Возможность продления срока действия токенов без перезаписи
- **Атомарность**: Separate SET/EXPIRE operations для лучшего контроля

### Access Control
- Токены доступны только владельцу аккаунта
- Нет доступа к токенам через GraphQL API
- Токены не хранятся в основной базе данных

### Provider Isolation
- Токены разных провайдеров хранятся отдельно
- Удаление токенов одного провайдера не влияет на другие
- Поддержка множественных OAuth подключений

## Integration Examples

### OAuth Login Flow
```python
# После успешной авторизации через OAuth провайдера
async def handle_oauth_callback(user_id: int, provider: str, tokens: dict):
    # Сохраняем токены в Redis
    await OAuthTokenStorage.store_access_token(
        user_id=user_id,
        provider=provider,
        access_token=tokens["access_token"],
        expires_in=tokens.get("expires_in", 3600)
    )

    if "refresh_token" in tokens:
        await OAuthTokenStorage.store_refresh_token(
            user_id=user_id,
            provider=provider,
            refresh_token=tokens["refresh_token"]
        )
```

### Token Refresh
```python
async def refresh_oauth_token(user_id: int, provider: str):
    # Получаем refresh token
    refresh_data = await OAuthTokenStorage.get_refresh_token(user_id, provider)
    if not refresh_data:
        return False

    # Обмениваем refresh token на новый access token
    new_tokens = await exchange_refresh_token(
        provider, refresh_data["token"]
    )

    # Сохраняем новые токены
    return await OAuthTokenStorage.refresh_access_token(
        user_id=user_id,
        provider=provider,
        new_access_token=new_tokens["access_token"],
        expires_in=new_tokens.get("expires_in"),
        new_refresh_token=new_tokens.get("refresh_token")
    )
```

### API Integration
```python
async def make_oauth_request(user_id: int, provider: str, endpoint: str):
    # Получаем действующий access token
    token_data = await OAuthTokenStorage.get_access_token(user_id, provider)

    if not token_data:
        # Токен отсутствует, требуется повторная авторизация
        raise OAuthTokenMissing()

    # Делаем запрос к API провайдера
    headers = {"Authorization": f"Bearer {token_data['token']}"}
    response = await httpx.get(endpoint, headers=headers)

    if response.status_code == 401:
        # Токен истек, пытаемся обновить
        if await refresh_oauth_token(user_id, provider):
            # Повторяем запрос с новым токеном
            token_data = await OAuthTokenStorage.get_access_token(user_id, provider)
            headers = {"Authorization": f"Bearer {token_data['token']}"}
            response = await httpx.get(endpoint, headers=headers)

    return response.json()
```

### TTL Monitoring and Management
```python
async def monitor_token_expiration(user_id: int, provider: str):
    """Мониторинг и управление сроком действия токенов"""

    # Получаем информацию о токенах
    info = await OAuthTokenStorage.get_token_info(user_id, provider)

    # Проверяем access token
    if info["access_token"]["exists"]:
        ttl = info["access_token"]["ttl"]
        if ttl < 300:  # Меньше 5 минут
            logger.warning(f"Access token expires soon: {ttl}s")
            # Автоматически обновляем токен
            await refresh_oauth_token(user_id, provider)

    # Проверяем refresh token
    if info["refresh_token"]["exists"]:
        ttl = info["refresh_token"]["ttl"]
        if ttl < 86400:  # Меньше 1 дня
            logger.warning(f"Refresh token expires soon: {ttl}s")
            # Уведомляем пользователя о необходимости повторной авторизации

async def extend_session_if_active(user_id: int, provider: str):
    """Продлевает сессию для активных пользователей"""

    # Проверяем активность пользователя
    if await is_user_active(user_id):
        # Продлеваем access token на 1 час
        success = await OAuthTokenStorage.extend_token_ttl(
            user_id, provider, "access", 3600
        )
        if success:
            logger.info(f"Extended access token for active user {user_id}")
```

## Migration from Database

Если у вас уже есть OAuth токены в базе данных, используйте этот скрипт для миграции:

```python
async def migrate_oauth_tokens():
    """Миграция OAuth токенов из БД в Redis"""
    with local_session() as session:
        # Предполагая, что токены хранились в таблице authors
        authors = session.query(Author).filter(
            or_(
                Author.provider_access_token.is_not(None),
                Author.provider_refresh_token.is_not(None)
            )
        ).all()

        for author in authors:
            # Получаем провайдер из oauth вместо старого поля oauth
            if author.oauth:
                for provider in author.oauth.keys():
                    if author.provider_access_token:
                        await OAuthTokenStorage.store_access_token(
                            user_id=author.id,
                            provider=provider,
                            access_token=author.provider_access_token
                        )

                    if author.provider_refresh_token:
                        await OAuthTokenStorage.store_refresh_token(
                            user_id=author.id,
                            provider=provider,
                            refresh_token=author.provider_refresh_token
                        )

        print(f"Migrated OAuth tokens for {len(authors)} users")
```

## Performance Benefits

### Redis Advantages
- **Скорость**: Доступ к токенам за микросекунды
- **Масштабируемость**: Не нагружает основную БД
- **Автоматическая очистка**: TTL убирает истекшие токены
- **Память**: Эффективное использование памяти Redis

### Reduced Database Load
- OAuth токены больше не записываются в основную БД
- Уменьшено количество записей в таблице authors
- Faster user queries без JOIN к токенам

## Monitoring and Maintenance

### Redis Memory Usage
```bash
# Проверка использования памяти OAuth токенами
redis-cli --scan --pattern "oauth_*" | wc -l
redis-cli memory usage oauth_access:123:google
```

### Cleanup Statistics
```python
# Периодическая очистка и логирование (опционально)
async def oauth_cleanup_job():
    cleaned = await OAuthTokenStorage.cleanup_expired_tokens()
    logger.info(f"OAuth cleanup completed, {cleaned} tokens processed")
```
