# Схема данных Redis в Discours.io

## Обзор

Redis используется как основное хранилище для кэширования, сессий, токенов и временных данных. Все ключи следуют структурированным паттернам для обеспечения консистентности и производительности.

## Принципы именования ключей

### Общие правила
- Использование двоеточия `:` как разделителя иерархии
- Формат: `{category}:{type}:{identifier}` или `{entity}:{property}:{value}`
- Константное время поиска через точные ключи
- TTL для всех временных данных

### Категории данных
1. **Аутентификация**: `session:*`, `oauth_*`, `env_vars:*`
2. **Кэш сущностей**: `author:*`, `topic:*`, `shout:*`
3. **Поиск**: `search_cache:*`
4. **Просмотры**: `migrated_views_*`, `viewed_*`
5. **Уведомления**: publish/subscribe каналы

## 1. Система аутентификации

### 1.1 Сессии пользователей

#### Структура ключей
```
session:{user_id}:{jwt_token}        # HASH - данные сессии
user_sessions:{user_id}              # SET - список активных токенов пользователя
{user_id}-{username}-{token}         # STRING - legacy формат (deprecated)
```

#### Данные сессии (HASH)
```redis
HGETALL session:123:eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```
**Поля:**
- `user_id`: ID пользователя (string)
- `username`: Имя пользователя (string)
- `token_type`: "session" (string)
- `created_at`: Unix timestamp создания (string)
- `last_activity`: Unix timestamp последней активности (string)
- `auth_data`: JSON строка с данными авторизации (string, optional)
- `device_info`: JSON строка с информацией об устройстве (string, optional)

**TTL**: 30 дней (2592000 секунд)

#### Список токенов пользователя (SET)
```redis
SMEMBERS user_sessions:123
```
**Содержимое**: JWT токены активных сессий пользователя
**TTL**: 30 дней

### 1.2 OAuth токены

#### Структура ключей
```
oauth_access:{user_id}:{provider}    # STRING - access токен
oauth_refresh:{user_id}:{provider}   # STRING - refresh токен
oauth_state:{state}                  # HASH - временное состояние OAuth flow
```

#### Access токены
**Провайдеры**: `google`, `github`, `facebook`, `twitter`, `telegram`, `vk`, `yandex`
**TTL**: 1 час (3600 секунд)
**Пример**:
```redis
GET oauth_access:123:google
# Возвращает: access_token_string
```

#### Refresh токены
**TTL**: 30 дней (2592000 секунд)
**Пример**:
```redis
GET oauth_refresh:123:google
# Возвращает: refresh_token_string
```

#### OAuth состояние (временное)
```redis
HGETALL oauth_state:a1b2c3d4e5f6
```
**Поля:**
- `redirect_uri`: URL для перенаправления после авторизации
- `csrf_token`: CSRF защита
- `provider`: Провайдер OAuth
- `created_at`: Время создания

**TTL**: 10 минут (600 секунд)

### 1.3 Токены подтверждения

#### Структура ключей
```
verification:{user_id}:{type}:{token}    # HASH - данные токена подтверждения
```

#### Типы подтверждения
- `email_verification`: Подтверждение email
- `phone_verification`: Подтверждение телефона
- `password_reset`: Сброс пароля
- `email_change`: Смена email

**Поля токена**:
- `user_id`: ID пользователя
- `token_type`: Тип токена
- `verification_type`: Тип подтверждения
- `created_at`: Время создания
- `data`: JSON с дополнительными данными

**TTL**: 1 час (3600 секунд)

## 2. Переменные окружения

### Структура ключей
```
env_vars:{variable_name}             # STRING - значение переменной
```

### Примеры переменных
```redis
GET env_vars:JWT_SECRET              # Секретный ключ JWT
GET env_vars:REDIS_URL               # URL Redis
GET env_vars:OAUTH_GOOGLE_CLIENT_ID  # Google OAuth Client ID
GET env_vars:FEATURE_REGISTRATION    # Флаг функции регистрации
```

**Категории переменных**:
- **database**: DB_URL, POSTGRES_*
- **auth**: JWT_SECRET, OAUTH_*
- **redis**: REDIS_URL, REDIS_HOST, REDIS_PORT
- **search**: SEARCH_API_KEY, ELASTICSEARCH_URL
- **integrations**: GOOGLE_ANALYTICS_ID, SENTRY_DSN, SMTP_*
- **security**: CORS_ORIGINS, ALLOWED_HOSTS
- **logging**: LOG_LEVEL, DEBUG
- **features**: FEATURE_*

**TTL**: Без ограничения (постоянное хранение)

## 3. Кэш сущностей

### 3.1 Авторы (пользователи)

#### Структура ключей
```
author:id:{author_id}                # STRING - JSON данные автора
author:slug:{author_slug}            # STRING - ID автора по slug
author:followers:{author_id}         # STRING - JSON массив подписчиков
author:follows-topics:{author_id}    # STRING - JSON массив отслеживаемых тем
author:follows-authors:{author_id}   # STRING - JSON массив отслеживаемых авторов
author:follows-shouts:{author_id}    # STRING - JSON массив отслеживаемых публикаций
```

#### Данные автора (JSON)
```json
{
  "id": 123,
  "email": "user@example.com",
  "name": "Имя Пользователя",
  "slug": "username",
  "pic": "https://example.com/avatar.jpg",
  "bio": "Описание автора",
  "email_verified": true,
  "created_at": 1640995200,
  "updated_at": 1640995200,
  "last_seen": 1640995200,
  "stat": {
    "topics": 15,
    "authors": 8,
    "shouts": 42
  }
}
```

#### Подписчики автора
```json
[123, 456, 789]  // Массив ID подписчиков
```

#### Подписки автора
```json
// author:follows-topics:123
[1, 5, 10, 15]  // ID отслеживаемых тем

// author:follows-authors:123
[45, 67, 89]    // ID отслеживаемых авторов

// author:follows-shouts:123
[101, 102, 103] // ID отслеживаемых публикаций
```

**TTL**: Без ограничения (инвалидация при изменениях)

### 3.2 Темы

#### Структура ключей
```
topic:id:{topic_id}                  # STRING - JSON данные темы
topic:slug:{topic_slug}              # STRING - JSON данные темы
topic:authors:{topic_id}             # STRING - JSON массив авторов темы
topic:followers:{topic_id}           # STRING - JSON массив подписчиков темы
topic_shouts_{topic_id}              # STRING - JSON массив публикаций темы (legacy)
```

#### Данные темы (JSON)
```json
{
  "id": 5,
  "title": "Название темы",
  "slug": "tema-slug",
  "description": "Описание темы",
  "pic": "https://example.com/topic.jpg",
  "community": 1,
  "created_at": 1640995200,
  "updated_at": 1640995200,
  "stat": {
    "shouts": 150,
    "authors": 25,
    "followers": 89
  }
}
```

#### Авторы темы
```json
[123, 456, 789]  // ID авторов, писавших в теме
```

#### Подписчики темы
```json
[111, 222, 333, 444]  // ID подписчиков темы
```

**TTL**: Без ограничения (инвалидация при изменениях)

### 3.3 Публикации (Shouts)

#### Структура ключей
```
shouts:{params_hash}                 # STRING - JSON массив публикаций
topic_shouts_{topic_id}              # STRING - JSON массив публикаций темы
```

#### Примеры ключей публикаций
```
shouts:limit=20:offset=0:sort=created_at  # Последние публикации
shouts:author=123:limit=10                # Публикации автора
shouts:topic=5:featured=true              # Рекомендуемые публикации темы
```

**TTL**: 5 минут (300 секунд)

## 4. Поисковый кэш

### Структура ключей
```
search_cache:{normalized_query}      # STRING - JSON результаты поиска
```

### Нормализация запроса
- Приведение к нижнему регистру
- Удаление лишних пробелов
- Сортировка параметров

### Данные поиска (JSON)
```json
{
  "query": "поисковый запрос",
  "results": [
    {
      "type": "shout",
      "id": 123,
      "title": "Заголовок публикации",
      "slug": "publication-slug",
      "score": 0.95
    }
  ],
  "total": 15,
  "cached_at": 1640995200
}
```

**TTL**: 10 минут (600 секунд)

## 5. Система просмотров

### Структура ключей
```
migrated_views_{timestamp}           # HASH - просмотры публикаций
migrated_views_slugs                 # HASH - маппинг slug -> id
viewed:{shout_id}                    # STRING - счетчик просмотров
```

### Мигрированные просмотры (HASH)
```redis
HGETALL migrated_views_1640995200
```
**Поля**:
- `{shout_id}`: количество просмотров (string)
- `_timestamp`: время создания записи
- `_total`: общее количество записей

### Маппинг slug -> ID
```redis
HGETALL migrated_views_slugs
```
**Поля**: `{shout_slug}` -> `{shout_id}`

**TTL**: Без ограничения (данные аналитики)

## 6. Pub/Sub каналы

### Каналы уведомлений
```
notifications:{user_id}              # Персональные уведомления
notifications:global                 # Глобальные уведомления
notifications:topic:{topic_id}       # Уведомления темы
notifications:shout:{shout_id}       # Уведомления публикации
```

### Структура сообщения (JSON)
```json
{
  "type": "notification_type",
  "user_id": 123,
  "entity_type": "shout",
  "entity_id": 456,
  "action": "created|updated|deleted",
  "data": {
    "title": "Заголовок",
    "author": "Автор"
  },
  "timestamp": 1640995200
}
```

## 7. Временные данные

### Ключи блокировок
```
lock:{operation}:{entity_id}         # STRING - блокировка операции
```

**TTL**: 30 секунд (автоматическое снятие блокировки)

### Ключи состояния
```
state:{process}:{identifier}         # HASH - состояние процесса
```

**TTL**: От 1 минуты до 1 часа в зависимости от процесса

## 8. Мониторинг и статистика

### Ключи метрик
```
metrics:{metric_name}:{period}       # STRING - значение метрики
stats:{entity}:{timeframe}           # HASH - статистика сущности
```

### Примеры метрик
```
metrics:active_sessions:hourly       # Количество активных сессий
metrics:cache_hits:daily             # Попадания в кэш за день
stats:topics:weekly                  # Статистика тем за неделю
```

**TTL**: От 1 часа до 30 дней в зависимости от типа метрики

## 9. Оптимизация и производительность

### Пакетные операции
Используются Redis pipelines для атомарных операций:
```python
# Пример создания сессии
commands = [
    ("hset", (token_key, "user_id", user_id)),
    ("hset", (token_key, "created_at", timestamp)),
    ("expire", (token_key, ttl)),
    ("sadd", (user_tokens_key, token)),
]
await redis.execute_pipeline(commands)
```

### Стратегии кэширования
1. **Write-through**: Немедленное обновление кэша при изменении данных
2. **Cache-aside**: Lazy loading с обновлением при промахе
3. **Write-behind**: Отложенная запись в БД

### Инвалидация кэша
- **Точечная**: Удаление конкретных ключей при изменениях
- **По префиксу**: Массовое удаление связанных ключей
- **TTL**: Автоматическое истечение для временных данных

## 10. Мониторинг

### Команды диагностики
```bash
# Статистика использования памяти
redis-cli info memory

# Количество ключей по типам
redis-cli --scan --pattern "session:*" | wc -l
redis-cli --scan --pattern "author:*" | wc -l
redis-cli --scan --pattern "topic:*" | wc -l

# Размер конкретного ключа
redis-cli memory usage session:123:token...

# Анализ истечения ключей
redis-cli --scan --pattern "*" | xargs -I {} redis-cli ttl {}
```

### Проблемы и решения
1. **Память**: Использование TTL для временных данных
2. **Производительность**: Pipeline операции, connection pooling
3. **Консистентность**: Транзакции для критических операций
4. **Масштабирование**: Шардирование по user_id для сессий

## 11. Безопасность

### Принципы
- TTL для всех временных данных предотвращает накопление мусора
- Раздельное хранение секретных данных (токены) и публичных (кэш)
- Использование pipeline для атомарных операций
- Регулярная очистка истекших ключей

### Рекомендации
- Мониторинг использования памяти Redis
- Backup критичных данных (переменные окружения)
- Ограничение размера значений для предотвращения OOM
- Использование отдельных баз данных для разных типов данных
