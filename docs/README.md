# Документация проекта

## Модули

### Система авторизации (v0.5.1)

**Новая архитектура после рефакторинга:**

#### Основная документация
- **[Полная документация системы авторизации](auth-system.md)** - Обзор всех компонентов
- **[Архитектура и диаграммы](auth-architecture.md)** - Схемы потоков данных и компонентов
- **[Руководство по миграции](auth-migration.md)** - Переход на новую версию
- **[Система безопасности](security.md)** - Управление паролями и email
- **[OAuth управление](oauth.md)** - OAuth провайдеры и токены
- **[Система подписок](follower.md)** - Подписки пользователей

#### Основные возможности
- **Модульная архитектура токенов**:
  - `SessionTokenManager` - управление сессиями
  - `VerificationTokenManager` - токены подтверждения
  - `OAuthTokenManager` - OAuth токены
  - `BatchTokenOperations` - пакетные операции
  - `TokenMonitoring` - мониторинг и статистика
- **OAuth провайдеры**: Google, GitHub, Facebook, X, Telegram, VK, Yandex
- **Система разрешений (RBAC)**: роли user/moderator/admin с детальными правами
- **Redis оптимизации**: Pipeline операции, connection pooling, автоматическая очистка
- **Безопасность**: bcrypt + SHA256, JWT HS256, PKCE для OAuth, защита от брутфорса

#### Производительность (v0.6.0)
- ✅ **50%** ускорение Redis операций (pipeline использование)
- ✅ **30%** снижение потребления памяти
- ✅ **Устранение** proxy overhead
- ✅ **Real-time** мониторинг и статистика
- ✅ **Type-safe** codebase (mypy clean)

#### Использование
```python
# Новый API (рекомендуется)
from auth.tokens.sessions import SessionTokenManager
from auth.tokens.monitoring import TokenMonitoring

# Создание сессии
sessions = SessionTokenManager()
token = await sessions.create_session(user_id, username=username)

# Мониторинг
monitoring = TokenMonitoring()
health = await monitoring.health_check()
stats = await monitoring.get_token_statistics()

# Совместимость (упрощенный фасад)
from auth.tokens.storage import TokenStorage
await TokenStorage.create_session(user_id, username=username)
```

#### Конфигурация
```python
# settings.py - JWT
JWT_SECRET_KEY = "your-secret-key"
JWT_EXPIRATION_HOURS = 720  # 30 дней

# Redis
REDIS_URL = "redis://localhost:6379/0"
REDIS_SOCKET_KEEPALIVE = True
REDIS_HEALTH_CHECK_INTERVAL = 30

# OAuth провайдеры
GOOGLE_CLIENT_ID = "..."
GITHUB_CLIENT_ID = "..."
VK_APP_ID = "..."
YANDEX_CLIENT_ID = "..."
# ... и другие
```

### Реакции и комментарии

Модуль обработки пользовательских реакций и комментариев.

Основные возможности:
- Создание, обновление и удаление реакций (лайки, дизлайки, комментарии)
- Иерархические комментарии с пагинацией корневых и дочерних
- Расчет статистики (счетчик комментариев, рейтинг)
- Автоматическое добавление/снятие статуса "featured" для публикаций
- Оптимизация запросов с использованием distinct() для предотвращения дублирования

Особенности реализации:
- Физическое удаление рейтинговых реакций и логическое удаление комментариев (поле deleted_at)
- Использование distinct() для предотвращения дублирования результатов при JOIN с eager loading
- Эффективная обработка иерархических данных с помощью специализированных GraphQL запросов

Ключевые функции:
- `get_reactions_with_stat(q, limit, offset)` - получение реакций со статистикой
- `load_comments_branch(shout, parent_id, limit, offset, sort, children_limit, children_offset)` - загрузка иерархических комментариев с пагинацией

### Административный интерфейс

Основные возможности:
- Защищенный доступ только для авторизованных пользователей с ролью admin
- Автоматическая проверка прав пользователя
- Отдельная страница входа для неавторизованных пользователей
- Проверка доступа по email или правам в системе RBAC

Маршруты:
- `/admin` - административная панель с проверкой прав доступа

## Запуск сервера

### Стандартный запуск
```bash
python main.py
```

### Запуск с поддержкой HTTPS
Для локальной разработки с HTTPS используйте скрипт `run.py` с инструментом mkcert:

```bash
# Установите mkcert
# macOS:
brew install mkcert
# Linux:
# sudo apt install mkcert (или эквивалент для вашего дистрибутива)
# Windows:
# choco install mkcert

# Установите локальный CA
mkcert -install

# Запуск с HTTPS на порту 8000 через Granian
python run.py --https

# Запуск с HTTPS на другом порту
python run.py --https --port 8443

# Запуск с несколькими рабочими процессами
python run.py --https --workers 4

# Запуск с указанием домена для сертификата
python run.py --https --domain "localhost.localdomain"
```

При первом запуске будут автоматически сгенерированы доверенные локальные сертификаты с помощью mkcert.

**Преимущества mkcert:**
- Сертификаты распознаются браузером как доверенные (нет предупреждений)
- Работает на всех платформах (macOS, Linux, Windows)
- Простая установка и настройка
