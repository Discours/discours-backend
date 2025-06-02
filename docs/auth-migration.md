# Миграция системы авторизации

## Обзор изменений

Система авторизации была полностью переработана для улучшения производительности, безопасности и поддерживаемости:

### Основные изменения
- ✅ Упрощена архитектура токенов (убрана прокси-логика)
- ✅ Исправлены проблемы с типами (mypy clean)
- ✅ Оптимизированы Redis операции
- ✅ Добавлена система мониторинга токенов
- ✅ Улучшена производительность OAuth
- ✅ Удалены deprecated компоненты

## Миграция кода

### TokenStorage API

#### Было (deprecated):
```python
# Старый универсальный API
await TokenStorage.create_token("session", user_id, data, ttl)
await TokenStorage.get_token_data("session", token)
await TokenStorage.validate_token(token, "session")
await TokenStorage.revoke_token("session", token)
```

#### Стало (рекомендуется):
```python
# Прямое использование менеджеров
from auth.tokens.sessions import SessionTokenManager
from auth.tokens.verification import VerificationTokenManager
from auth.tokens.oauth import OAuthTokenManager

# Сессии
sessions = SessionTokenManager()
token = await sessions.create_session(user_id, username=username)
valid, data = await sessions.validate_session_token(token)
await sessions.revoke_session_token(token)

# Токены подтверждения
verification = VerificationTokenManager()
token = await verification.create_verification_token(user_id, "email_change", data)
valid, data = await verification.validate_verification_token(token)

# OAuth токены
oauth = OAuthTokenManager()
await oauth.store_oauth_tokens(user_id, "google", access_token, refresh_token)
```

#### Фасад TokenStorage (для совместимости):
```python
# Упрощенный фасад для основных операций
await TokenStorage.create_session(user_id, username=username)
await TokenStorage.verify_session(token)
await TokenStorage.refresh_session(user_id, old_token, device_info)
await TokenStorage.revoke_session(token)
```

### Redis Service

#### Обновленный API:
```python
from services.redis import redis

# Базовые операции
await redis.get(key)
await redis.set(key, value, ex=ttl)
await redis.delete(key)
await redis.exists(key)

# Pipeline операции
async with redis.pipeline(transaction=True) as pipe:
    await pipe.hset(key, field, value)
    await pipe.expire(key, seconds)
    results = await pipe.execute()

# Новые методы
await redis.scan(cursor, match=pattern, count=100)
await redis.scard(key)
await redis.ttl(key)
await redis.info(section="memory")
```

### Мониторинг токенов

#### Новые возможности:
```python
from auth.tokens.monitoring import TokenMonitoring

monitoring = TokenMonitoring()

# Статистика токенов
stats = await monitoring.get_token_statistics()
print(f"Active sessions: {stats['session_tokens']}")
print(f"Memory usage: {stats['memory_usage']} bytes")

# Health check
health = await monitoring.health_check()
if health["status"] == "healthy":
    print("Token system is healthy")

# Оптимизация памяти
results = await monitoring.optimize_memory_usage()
print(f"Cleaned {results['cleaned_expired']} expired tokens")
```

### Пакетные операции

#### Новые возможности:
```python
from auth.tokens.batch import BatchTokenOperations

batch = BatchTokenOperations()

# Массовая валидация
tokens = ["token1", "token2", "token3"]
results = await batch.batch_validate_tokens(tokens)
# {"token1": True, "token2": False, "token3": True}

# Массовый отзыв
revoked_count = await batch.batch_revoke_tokens(tokens)
print(f"Revoked {revoked_count} tokens")

# Очистка истекших
cleaned = await batch.cleanup_expired_tokens()
print(f"Cleaned {cleaned} expired tokens")
```

## Изменения в конфигурации

### Переменные окружения

#### Добавлены:
```bash
# Новые OAuth провайдеры
VK_APP_ID=your_vk_app_id
VK_APP_SECRET=your_vk_app_secret
YANDEX_CLIENT_ID=your_yandex_client_id
YANDEX_CLIENT_SECRET=your_yandex_client_secret

# Расширенные настройки Redis
REDIS_SOCKET_KEEPALIVE=true
REDIS_HEALTH_CHECK_INTERVAL=30
REDIS_SOCKET_TIMEOUT=5
```

#### Удалены:
```bash
# Больше не используются
OLD_TOKEN_FORMAT_SUPPORT=true  # автоматически определяется
TOKEN_CLEANUP_INTERVAL=3600    # заменено на on-demand cleanup
```

## Breaking Changes

### 1. Убраны deprecated методы

#### Удалено:
```python
# Эти методы больше не существуют
TokenStorage.create_token()        # -> используйте конкретные менеджеры
TokenStorage.get_token_data()      # -> используйте конкретные менеджеры
TokenStorage.validate_token()     # -> используйте конкретные менеджеры
TokenStorage.revoke_user_tokens() # -> используйте конкретные менеджеры
```

#### Альтернативы:
```python
# Для сессий
sessions = SessionTokenManager()
await sessions.create_session(user_id)
await sessions.revoke_user_sessions(user_id)

# Для verification
verification = VerificationTokenManager()
await verification.create_verification_token(user_id, "email", data)
await verification.revoke_user_verification_tokens(user_id)
```

### 2. Изменения в compat.py

Файл `auth/tokens/compat.py` удален. Если вы использовали `CompatibilityMethods`:

#### Миграция:
```python
# Было
from auth.tokens.compat import CompatibilityMethods
compat = CompatibilityMethods()
await compat.get(token_key)

# Стало
from services.redis import redis
result = await redis.get(token_key)
```

### 3. Изменения в типах

#### Обновленные импорты:
```python
# Было
from auth.tokens.storage import TokenType, TokenData

# Стало
from auth.tokens.types import TokenType, TokenData
```

## Рекомендации по миграции

### Поэтапная миграция

#### Шаг 1: Обновите импорты
```python
# Замените старые импорты
from auth.tokens.sessions import SessionTokenManager
from auth.tokens.verification import VerificationTokenManager
from auth.tokens.oauth import OAuthTokenManager
```

#### Шаг 2: Используйте конкретные менеджеры
```python
# Вместо универсального TokenStorage
# используйте специализированные менеджеры
sessions = SessionTokenManager()
```

#### Шаг 3: Добавьте мониторинг
```python
from auth.tokens.monitoring import TokenMonitoring

# Добавьте health checks в ваши endpoints
monitoring = TokenMonitoring()
health = await monitoring.health_check()
```

#### Шаг 4: Оптимизируйте батчевые операции
```python
from auth.tokens.batch import BatchTokenOperations

# Используйте batch операции для массовых действий
batch = BatchTokenOperations()
results = await batch.batch_validate_tokens(token_list)
```

### Тестирование миграции

#### Checklist:
- [ ] Все auth тесты проходят
- [ ] mypy проверки без ошибок
- [ ] OAuth провайдеры работают
- [ ] Session management функционирует
- [ ] Redis операции оптимизированы
- [ ] Мониторинг настроен

#### Команды для тестирования:
```bash
# Проверка типов
mypy .

# Запуск auth тестов
pytest tests/auth/ -v

# Проверка Redis подключения
python -c "
import asyncio
from services.redis import redis
async def test():
    result = await redis.ping()
    print(f'Redis connection: {result}')
asyncio.run(test())
"

# Health check системы токенов
python -c "
import asyncio
from auth.tokens.monitoring import TokenMonitoring
async def test():
    health = await TokenMonitoring().health_check()
    print(f'Token system health: {health}')
asyncio.run(test())
"
```

## Производительность

### Ожидаемые улучшения
- **50%** ускорение Redis операций (pipeline использование)
- **30%** снижение memory usage (оптимизированные структуры)
- **Elimination** of proxy overhead (прямое обращение к менеджерам)
- **Real-time** мониторинг и статистика

### Мониторинг после миграции
```python
# Регулярно проверяйте статистику
from auth.tokens.monitoring import TokenMonitoring

async def check_performance():
    monitoring = TokenMonitoring()
    stats = await monitoring.get_token_statistics()

    print(f"Session tokens: {stats['session_tokens']}")
    print(f"Memory usage: {stats['memory_usage'] / 1024 / 1024:.2f} MB")

    # Оптимизация при необходимости
    if stats['memory_usage'] > 100 * 1024 * 1024:  # 100MB
        results = await monitoring.optimize_memory_usage()
        print(f"Optimized: {results}")
```

## Поддержка

Если возникли проблемы при миграции:

1. **Проверьте логи** - все изменения логируются
2. **Запустите health check** - `TokenMonitoring().health_check()`
3. **Проверьте Redis** - подключение и память
4. **Откатитесь к TokenStorage фасаду** при необходимости

### Контакты
- **Issues**: GitHub Issues
- **Документация**: `/docs/auth-system.md`
- **Архитектура**: `/docs/auth-architecture.md`
