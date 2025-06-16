# Документация Discours.io API

## 🚀 Быстрый старт

### Запуск локально
```bash
# Стандартный запуск
python main.py

# С HTTPS (требует mkcert)
python dev.py
```

## 📚 Документация

### Авторизация и безопасность
- [Система авторизации](auth-system.md) - Токены, сессии, OAuth
- [Архитектура](auth-architecture.md) - Диаграммы и схемы
- [Миграция](auth-migration.md) - Переход на новую версию
- [Безопасность](security.md) - Пароли, email, RBAC
- [OAuth](oauth.md) - Google, GitHub, Facebook, X, Telegram, VK, Yandex
- [OAuth настройка](oauth-setup.md) - Инструкции по настройке OAuth провайдеров

### Функциональность
- [Система рейтингов](rating.md) - Лайки, дизлайки, featured статьи
- [Подписки](follower.md) - Follow/unfollow логика
- [Кэширование](caching.md) - Redis, производительность
- [Схема данных Redis](redis-schema.md) - Полная документация структур данных
- [Пагинация комментариев](comments-pagination.md) - Иерархические комментарии
- [Загрузка контента](load_shouts.md) - Оптимизированные запросы

### API и инфраструктура
- [API методы](api.md) - GraphQL эндпоинты
- [Функции системы](features.md) - Полный список возможностей

## ⚡ Ключевые возможности (v0.5.4)

### Авторизация
- **Модульная архитектура**: SessionTokenManager, VerificationTokenManager, OAuthTokenManager
- **OAuth провайдеры**: 7 поддерживаемых провайдеров с PKCE
- **RBAC**: user/moderator/admin роли
- **Производительность**: 50% ускорение Redis, 30% меньше памяти

### Nginx (упрощенная конфигурация)
- **KISS принцип**: ~60 строк вместо сложной конфигурации
- **Dokku дефолты**: Максимальное использование встроенных настроек
- **SSL/TLS**: TLS 1.2/1.3, HSTS, OCSP stapling
- **Статические файлы**: Кэширование на 1 год, gzip сжатие
- **Безопасность**: X-Frame-Options, X-Content-Type-Options

### Реакции и комментарии
- **Иерархические комментарии** с эффективной пагинацией
- **Физическое/логическое удаление** (рейтинги/комментарии)
- **Автоматический featured статус** на основе лайков
- **Distinct() оптимизация** для JOIN запросов

### Производительность
- **Redis pipeline операции** для пакетных запросов
- **Автоматическая очистка** истекших токенов
- **Connection pooling** и keepalive
- **Type-safe codebase** (mypy clean)

## 🔧 Конфигурация

```python
# JWT
JWT_SECRET_KEY = "your-secret-key"
JWT_EXPIRATION_HOURS = 720  # 30 дней

# Redis
REDIS_URL = "redis://localhost:6379/0"

# OAuth (необходимые провайдеры)
OAUTH_CLIENTS_GOOGLE_ID = "..."
OAUTH_CLIENTS_GITHUB_ID = "..."
# ... другие провайдеры
```

## 🛠 Использование API

```python
# Сессии
from auth.tokens.sessions import SessionTokenManager
sessions = SessionTokenManager()
token = await sessions.create_session(user_id, username=username)

# Мониторинг
from auth.tokens.monitoring import TokenMonitoring
monitoring = TokenMonitoring()
stats = await monitoring.get_token_statistics()
```
