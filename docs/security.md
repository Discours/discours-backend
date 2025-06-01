# Security System

## Overview
Система безопасности обеспечивает управление паролями и email адресами пользователей через специализированные GraphQL мутации с использованием Redis для хранения токенов.

## GraphQL API

### Мутации

#### updateSecurity
Универсальная мутация для смены пароля и/или email пользователя с полной валидацией и безопасностью.

**Parameters:**
- `email: String` - Новый email (опционально)
- `old_password: String` - Текущий пароль (обязательно для любых изменений)
- `new_password: String` - Новый пароль (опционально)

**Returns:**
```typescript
type SecurityUpdateResult {
  success: Boolean!
  error: String
  author: Author
}
```

**Примеры использования:**

```graphql
# Смена пароля
mutation {
  updateSecurity(
    old_password: "current123"
    new_password: "newPassword456"
  ) {
    success
    error
    author {
      id
      name
      email
    }
  }
}

# Смена email
mutation {
  updateSecurity(
    email: "newemail@example.com"
    old_password: "current123"
  ) {
    success
    error
    author {
      id
      name
      email
    }
  }
}

# Одновременная смена пароля и email
mutation {
  updateSecurity(
    email: "newemail@example.com"
    old_password: "current123"
    new_password: "newPassword456"
  ) {
    success
    error
    author {
      id
      name
      email
    }
  }
}
```

#### confirmEmailChange
Подтверждение смены email по токену, полученному на новый email адрес.

**Parameters:**
- `token: String!` - Токен подтверждения

**Returns:** `SecurityUpdateResult`

#### cancelEmailChange
Отмена процесса смены email.

**Returns:** `SecurityUpdateResult`

### Валидация и Ошибки

```typescript
const ERRORS = {
  NOT_AUTHENTICATED: "User not authenticated",
  INCORRECT_OLD_PASSWORD: "incorrect old password",
  PASSWORDS_NOT_MATCH: "New passwords do not match",
  EMAIL_ALREADY_EXISTS: "email already exists",
  INVALID_EMAIL: "Invalid email format",
  WEAK_PASSWORD: "Password too weak",
  SAME_PASSWORD: "New password must be different from current",
  VALIDATION_ERROR: "Validation failed",
  INVALID_TOKEN: "Invalid token",
  TOKEN_EXPIRED: "Token expired",
  NO_PENDING_EMAIL: "No pending email change"
}
```

## Логика смены email

1. **Инициация смены:**
   - Пользователь вызывает `updateSecurity` с новым email
   - Генерируется токен подтверждения `token_urlsafe(32)`
   - Данные смены email сохраняются в Redis с ключом `email_change:{user_id}`
   - Устанавливается автоматическое истечение токена (1 час)
   - Отправляется письмо на новый email с токеном

2. **Подтверждение:**
   - Пользователь получает письмо с токеном
   - Вызывает `confirmEmailChange` с токеном
   - Система проверяет токен и срок действия в Redis
   - Если токен валиден, email обновляется в базе данных
   - Данные смены email удаляются из Redis

3. **Отмена:**
   - Пользователь может отменить смену через `cancelEmailChange`
   - Данные смены email удаляются из Redis

## Redis Storage

### Хранение токенов смены email
```json
{
  "key": "email_change:{user_id}",
  "value": {
    "user_id": 123,
    "old_email": "old@example.com",
    "new_email": "new@example.com",
    "token": "random_token_32_chars",
    "expires_at": 1640995200
  },
  "ttl": 3600  // 1 час
}
```

### Хранение OAuth токенов
```json
{
  "key": "oauth_access:{user_id}:{provider}",
  "value": {
    "token": "oauth_access_token",
    "provider": "google",
    "user_id": 123,
    "created_at": 1640995200,
    "expires_in": 3600,
    "scope": "profile email"
  },
  "ttl": 3600  // время из expires_in или 1 час по умолчанию
}
```

```json
{
  "key": "oauth_refresh:{user_id}:{provider}",
  "value": {
    "token": "oauth_refresh_token",
    "provider": "google",
    "user_id": 123,
    "created_at": 1640995200
  },
  "ttl": 2592000  // 30 дней по умолчанию
}
```

### Преимущества Redis хранения
- **Автоматическое истечение**: TTL в Redis автоматически удаляет истекшие токены
- **Производительность**: Быстрый доступ к данным токенов
- **Масштабируемость**: Не нагружает основную базу данных
- **Безопасность**: Токены не хранятся в основной БД
- **Простота**: Не требует миграции схемы базы данных
- **OAuth токены**: Централизованное управление токенами всех OAuth провайдеров

## Безопасность

### Требования к паролю
- Минимум 8 символов
- Не может совпадать с текущим паролем

### Аутентификация
- Все операции требуют валидного токена аутентификации
- Старый пароль обязателен для подтверждения личности

### Валидация email
- Проверка формата email через регулярное выражение
- Проверка уникальности email в системе
- Защита от race conditions при смене email

### Токены безопасности
- Генерация токенов через `secrets.token_urlsafe(32)`
- Автоматическое истечение через 1 час
- Удаление токенов после использования или отмены

## Database Schema

Система не требует изменений в схеме базы данных. Все токены и временные данные хранятся в Redis.

### Защищенные поля
Следующие поля показываются только владельцу аккаунта:
- `email`
- `password`
