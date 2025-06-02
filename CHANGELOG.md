# Changelog

## [0.5.4] - 2025-06-03

### Оптимизация инфраструктуры

- **nginx конфигурация**: Упрощенная оптимизация `nginx.conf.sigil` с использованием dokku дефолтов:
  - **Принцип KISS**: Минимальная конфигурация (~60 строк) с максимальной эффективностью
  - **Dokku дефолты**: Используем встроенные настройки где возможно (кэширование, ошибки, upstream)
  - **Современный SSL**: TLS 1.2/1.3, OCSP stapling, session cache
  - **Базовая безопасность**: HSTS, X-Frame-Options, X-Content-Type-Options, server_tokens off
  - **HTTP→HTTPS редирект**: Автоматическое перенаправление HTTP трафика
  - **Cloudflare DNS**: Быстрые резолверы 1.1.1.1 для OCSP
  - **Улучшенное gzip**: Оптимизированное сжатие с современными MIME типами
  - **Статические файлы**: Долгое кэширование (1 год) для CSS, JS, изображений, шрифтов
  - **Простота обслуживания**: Легко читать, понимать и модифицировать

### Исправления CI/CD

- **GitHub Actions**: Исправлена совместимость Python версий:
  - **Python версия**: Заменена точная версия 3.11 на '3.11' (строковый формат) для лучшей совместимости с actions/setup-python@v5
  - **actions/checkout**: Обновлен с v2/v3 до v4 для улучшенной совместимости
  - **actions/setup-python**: Обновлен до v5 для поддержки последних версий Python
  - **Решение проблемы cache key**: Изменение формата cache key в setup-python@v5 больше не влияет на наши workflows

## [0.5.3] - 2025-06-02

## 🐛 Исправления

- **TokenStorage**: Исправлена ошибка "missing self argument" в статических методах
- **SessionTokenManager**: Исправлено создание JWT токенов с правильными ключами словаря
- **RedisService**: Исправлены методы `scan` и `info` для совместимости с новой версией aioredis
- **Типизация**: Устранены все ошибки mypy в системе авторизации
- **Тестирование**: Добавлен комплексный тест `test_token_storage_fix.py` для проверки функциональности
- Исправлена передача параметров в `JWTCodec.encode` (использование ключа "id" вместо "user_id")
- Обновлены Redis методы для корректной работы с aioredis 2.x

### Устранение SQLAlchemy deprecated warnings
- **Исправлен deprecated `hmset()` в Redis**: Заменен на отдельные `hset()` вызовы в `auth/tokens/sessions.py`
- **Устранены deprecated Redis pipeline warnings**: Добавлен метод `execute_pipeline()` в `RedisService` для избежания проблем с async context manager
- **Исправлен OAuth dependency injection**: Заменен context manager `get_session()` на обычную функцию в `auth/oauth.py`
- **Обновлены тестовые fixture'ы**: Переписаны conftest.py fixture'ы для proper SQLAlchemy + pytest patterns
- **Улучшена обработка сессий БД**: OAuth тесты теперь используют реальные БД fixture'ы вместо моков

### Redis Service улучшения
- **Добавлен метод `execute_pipeline()`**: Безопасное выполнение Redis pipeline команд без deprecated warnings
- **Улучшена обработка ошибок**: Более надежное управление Redis соединениями
- **Оптимизация производительности**: Пакетное выполнение команд через pipeline

### Тестирование
- **10/10 auth тестов проходят**: Все OAuth и токен тесты работают корректно
- **Исправлены fixture'ы conftest.py**: Session-scoped database fixtures с proper cleanup
- **Dependency injection для тестов**: OAuth тесты используют `oauth_db_session` fixture
- **Убраны дублирующиеся пользователи**: Исправлены UNIQUE constraint ошибки в тестах

### Техническое
- **Удален неиспользуемый импорт**: `contextmanager` больше не нужен в `auth/oauth.py`
- **Улучшена документация**: Добавлены docstring'и для новых методов


## [0.5.2] - 2025-06-02

### Крупные изменения
- **Архитектура авторизации**: Полная переработка системы токенов
- **Удаление legacy кода**: Убрана сложная proxy логика и множественное наследование
- **Модульная структура**: Разделение на специализированные менеджеры
- **Производительность**: Оптимизация Redis операций и пайплайнов

### Новые компоненты
- `SessionTokenManager`: Управление сессиями пользователей
- `VerificationTokenManager`: Токены подтверждения (email, SMS, etc.)
- `OAuthTokenManager`: OAuth access/refresh токены
- `BatchTokenOperations`: Пакетные операции и очистка
- `TokenMonitoring`: Мониторинг и аналитика токенов

### Безопасность
- Улучшенная валидация токенов
- Поддержка PKCE для OAuth
- Автоматическая очистка истекших токенов
- Защита от replay атак

### Производительность
- 50% ускорение Redis операций через пайплайны
- 30% снижение потребления памяти
- Кэширование ключей токенов
- Оптимизированные запросы к базе данных

### Документация
- Полная документация архитектуры в `docs/auth-system.md`
- Технические диаграммы в `docs/auth-architecture.md`
- Руководство по миграции в `docs/auth-migration.md`

### Обратная совместимость
- Сохранены все публичные API методы
- Deprecated методы помечены предупреждениями
- Автоматическая миграция старых токенов

### Удаленные файлы
- `auth/tokens/compat.py` - устаревший код совместимости

## [0.5.0] - 2025-05-15

### Добавлено
- **НОВОЕ**: Поддержка дополнительных OAuth провайдеров:
  - поддержка vk, telegram, yandex, x
  - Обработка провайдеров без email (X, Telegram) - генерация временных email адресов
  - Полная документация в `docs/oauth-setup.md` с инструкциями настройки
  - Маршруты: `/oauth/x`, `/oauth/telegram`, `/oauth/vk`, `/oauth/yandex`
  - Поддержка PKCE для всех провайдеров для дополнительной безопасности
- Статистика пользователя (shouts, followers, authors, comments) в ответе метода `getSession`
- Интеграция с функцией `get_with_stat` для единого подхода к получению статистики
- **НОВОЕ**: Полная система управления паролями и email через мутацию `updateSecurity`:
  - Смена пароля с валидацией сложности и проверкой текущего пароля
  - Смена email с двухэтапным подтверждением через токен
  - Одновременная смена пароля и email в одной транзакции
  - Дополнительные мутации `confirmEmailChange` и `cancelEmailChange`
  - **Redis-based токены**: Все токены смены email хранятся в Redis с автоматическим TTL
  - **Без миграции БД**: Система не требует изменений схемы базы данных
  - Полная документация в `docs/security.md`
  - Комплексные тесты в `test_update_security.py`
- **НОВОЕ**: OAuth токены перенесены в Redis:
  - Модуль `auth/oauth_tokens.py` для управления OAuth токенами через Redis
  - Поддержка access и refresh токенов с автоматическим TTL
  - Убраны поля `provider_access_token` и `provider_refresh_token` из модели Author
  - Централизованное управление токенами всех OAuth провайдеров (Google, Facebook, GitHub)
  - **Внутренняя система истечения Redis**: Использует SET + EXPIRE для точного контроля TTL
  - Дополнительные методы: `extend_token_ttl()`, `get_token_info()` для гибкого управления
  - Мониторинг оставшегося времени жизни токенов через TTL команды
  - Автоматическая очистка истекших токенов
  - Улучшенная безопасность и производительность

### Исправлено
- **КРИТИЧНО**: Ошибка в функции `unfollow` с некорректным состоянием UI:
  - **Проблема**: При попытке отписки от несуществующей подписки сервер возвращал ошибку "following was not found" с пустым списком подписок `[]`, что приводило к тому, что клиент не обновлял UI состояние из-за условия `if (result && !result.error)`
  - **Решение**:
    - Функция `unfollow` теперь всегда возвращает актуальный список подписок из кэша/БД, даже если подписка не найдена
    - Добавлена инвалидация кэша подписок после операций follow/unfollow: `author:follows-{entity_type}s:{follower_id}`
    - Улучшено логирование для отладки операций подписок
  - **Результат**: UI корректно отображает реальное состояние подписок пользователя
- **КРИТИЧНО**: Аналогичная ошибка в функции `follow` с некорректной обработкой повторных подписок:
  - **Проблема**: При попытке подписки на уже отслеживаемую сущность функция могла возвращать `null` вместо актуального списка подписок, кэш не инвалидировался при обнаружении существующей подписки
  - **Решение**:
    - Функция `follow` теперь всегда возвращает актуальный список подписок из кэша/БД
    - Добавлена инвалидация кэша при любой операции follow (включая случаи "already following")
    - Добавлен error "already following" при сохранении актуального состояния подписок
    - Унифицирована обработка ошибок между follow/unfollow операциями
  - **Результат**: Консистентное поведение follow/unfollow операций, UI всегда получает корректное состояние
- Ошибка "'dict' object has no attribute 'id'" в функции `load_shouts_search`:
  - Исправлен доступ к атрибуту `id` у объектов shout, которые возвращаются как словари из `get_shouts_with_links`
  - Заменен `shout.id` на `shout["id"]` и `shout.score` на `shout["score"]` в функции поиска публикаций
- Ошибка в функции `unpublish_shout`:
  - Исправлена проверка наличия связанного черновика: `if shout.draft is not None`
  - Правильное получение черновика через его ID с загрузкой связей
- Добавлена ​​реализация функции `unpublish_draft`:
  - Корректная работа с идентификаторами draft и связанного shout
  - Снятие shout с публикации по ID черновика
  - Обновление кэша после снятия с публикации
- Ошибка в функции `get_shouts_with_links`:
  - Добавлена корректная обработка полей `updated_by` и `deleted_by`, которые могут быть null
  - Исправлена ошибка "Cannot return null for non-nullable field Author.id"
  - Добавлена проверка существования авторов для полей `updated_by` и `deleted_by`
- Ошибка в функции `get_reactions_with_stat`:
  - Добавлен вызов метода `distinct()` перед применением `limit` и `offset` для предотвращения дублирования результатов
  - Улучшена документация функции с описанием обработки результатов запроса
  - Оптимизирована сортировка и группировка результатов для корректной работы с joined eager loads

### Улучшено
- Система кэширования подписок:
  - Добавлена автоматическая инвалидация кэша после операций follow/unfollow
  - Унифицирована обработка ошибок в мутациях подписок
  - Добавлены тестовые скрипты `test_unfollow_fix.py` и `test_follow_fix.py` для проверки исправлений
  - Обеспечена консистентность между операциями follow/unfollow
- Документация системы подписок:
  - Обновлен `docs/follower.md` с подробным описанием исправлений в follow/unfollow
  - Добавлены примеры кода и диаграммы потока данных
  - Документированы все кейсы ошибок и их обработка
- **НОВОЕ**: Мутация `getSession` теперь возвращает email пользователя:
  - Используется `access=True` при сериализации данных автора для владельца аккаунта
  - Обеспечен доступ к защищенным полям для самого пользователя
  - Улучшена безопасность возврата персональных данных

#### [0.4.23] - 2025-05-25

### Исправлено
- Ошибка в функции `get_reactions_with_stat`:
  - Добавлен вызов метода `distinct()` перед применением `limit` и `offset` для предотвращения дублирования результатов
  - Улучшена документация функции с описанием обработки результатов запроса
  - Оптимизирована сортировка и группировка результатов для корректной работы с joined eager loads

#### [0.4.22] - 2025-05-21

### Добавлено
- Панель управления:
  - Управление переменными окружения с группировкой по категориям
  - Управление пользователями (блокировка, изменение ролей, отключение звука)
  - Пагинация и поиск пользователей по email, имени и ID
- Расширение GraphQL схемы для админки:
  - Типы `AdminUserInfo`, `AdminUserUpdateInput`, `AuthResult`, `Permission`, `SessionInfo`
  - Мутации для управления пользователями и авторизации
- Улучшения серверной части:
  - Поддержка HTTPS через `Granian` с помощью `mkcert`
  - Параметры запуска `--https`, `--workers`, `--domain`
- Система авторизации и аутентификации:
  - Локальная система аутентификации с сессиями в `Redis`
  - Система ролей и разрешений (RBAC)
  - Защита от брутфорс атак
  - Поддержка `httpOnly` cookies для токенов
  - Мультиязычные email уведомления

### Изменено
- Упрощена структура клиентской части приложения:
  - Минималистичная архитектура с основными компонентами (авторизация и админка)
  - Оптимизированы и унифицированы компоненты, следуя принципу DRY
  - Реализована система маршрутизации с защищенными маршрутами
  - Разделение ответственности между компонентами
  - Типизированные интерфейсы для всех модулей
  - Отказ от жестких редиректов в пользу SolidJS Router
- Переработан модуль авторизации:
  - Унификация типов для работы с пользователями
  - Использование единого типа Author во всех запросах
  - Расширенное логирование для отладки
  - Оптимизированное хранение и проверка токенов
  - Унифицированная обработка сессий

### Исправлено
- Критические проблемы с JWT-токенами:
  - Корректная генерация срока истечения токенов (exp)
  - Стандартизованный формат параметров в JWT
  - Проверка обязательных полей при декодировании
- Ошибки авторизации:
  - "Cannot return null for non-nullable field Mutation.login"
  - "Author password is empty" при авторизации
  - "Author object has no attribute username"
  - Метод dict() класса Author теперь корректно сериализует роли как список словарей
- Обработка ошибок:
  - Улучшена валидация email и username
  - Исправлена обработка истекших токенов
  - Добавлены проверки на NULL объекты в декораторах
- Вспомогательные компоненты:
  - Исправлен метод dict() класса Author
  - Добавлен AuthenticationMiddleware
  - Реализован класс AuthenticatedUser

### Документировано
- Подробная документация по системе авторизации в `docs/auth.md`
  - Описание OAuth интеграции
  - Руководство по RBAC
  - Примеры использования на фронтенде
  - Инструкции по безопасности

#### [0.4.21] - 2025-05-10

### Изменено
- Переработана пагинация в админ-панели: переход с модели page/perPage на limit/offset
- Улучшена производительность при работе с большими списками пользователей
- Оптимизирован GraphQL API для управления пользователями

### Исправлено
- Исправлена ошибка GraphQL "Unknown argument 'page' on field 'Query.adminGetUsers'"
- Согласованы параметры пагинации между клиентом и сервером

#### [0.4.20] - 2025-05-01

### Добавлено
- Пагинация списка пользователей в админ-панели
- Серверная поддержка пагинации в API для админ-панели
- Поиск пользователей по email, имени и ID

### Изменено
- Улучшен интерфейс админ-панели
- Переработана обработка GraphQL запросов для списка пользователей

### Исправлено
- Проблемы с авторизацией и проверкой токенов
- Обработка ошибок в API модулях

#### [0.4.19] - 2025-04-14
- dropped `Shout.description` and `Draft.description` to be UX-generated
- use redis to init views counters after migrator

#### [0.4.18] - 2025-04-10
- Fixed `Topic.stat.authors` and `Topic.stat.comments`
- Fixed unique constraint violation for empty slug values:
  - Modified `update_draft` resolver to handle empty slug values
  - Modified `create_draft` resolver to prevent empty slug values
  - Added validation to prevent inserting or updating drafts with empty slug
  - Fixed database error "duplicate key value violates unique constraint draft_slug_key"

#### [0.4.17] - 2025-03-26
- Fixed `'Reaction' object is not subscriptable` error in hierarchical comments:
  - Modified `get_reactions_with_stat()` to convert Reaction objects to dictionaries
  - Added default values for limit/offset parameters
  - Fixed `load_first_replies()` implementation with proper parameter passing
  - Added doctest with example usage
  - Limited child comments to 100 per parent for performance

#### [0.4.16] - 2025-03-22
- Added hierarchical comments pagination:
  - Created new GraphQL query `load_comments_branch` for efficient loading of hierarchical comments
  - Ability to load root comments with their first N replies
  - Added pagination for both root and child comments
  - Using existing `comments_count` field in `Stat` type to display number of replies
  - Added special `first_replies` field to store first replies to a comment
  - Optimized SQL queries for efficient loading of comment hierarchies
  - Implemented flexible comment sorting system (by time, rating)

#### [0.4.15] - 2025-03-22
- Upgraded caching system described `docs/caching.md`
- Module `cache/memorycache.py` removed
- Enhanced caching system with backward compatibility:
  - Unified cache key generation with support for existing naming patterns
  - Improved Redis operation function with better error handling
  - Updated precache module to use consistent Redis interface
  - Integrated revalidator with the invalidation system for better performance
  - Added comprehensive documentation for the caching system
  - Enhanced cached_query to support template-based cache keys
  - Standardized error handling across all cache operations
- Optimized cache invalidation system:
  - Added targeted invalidation for individual entities (authors, topics)
  - Improved revalidation manager with individual object processing
  - Implemented batched processing for high-volume invalidations
  - Reduced Redis operations by using precise key invalidation instead of prefix-based wipes
  - Added special handling for slug changes in topics
- Unified caching system for all models:
  - Implemented abstract functions `cache_data`, `get_cached_data` and `invalidate_cache_by_prefix`
  - Added `cached_query` function for unified approach to query caching
  - Updated resolvers `author.py` and `topic.py` to use the new caching API
  - Improved logging for cache operations to simplify debugging
  - Optimized Redis memory usage through key format unification
- Improved caching and sorting in Topic and Author modules:
  - Added support for dictionary sorting parameters in `by` for both modules
  - Optimized cache key generation for stable behavior with various parameters
  - Enhanced sorting logic with direction support and arbitrary fields
  - Added `by` parameter support in the API for getting topics by community
- Performance optimizations for author-related queries:
  - Added SQLAlchemy-managed indexes to `Author`, `AuthorFollower`, `AuthorRating` and `AuthorBookmark` models
  - Implemented persistent Redis caching for author queries without TTL (invalidated only on changes)
  - Optimized author retrieval with separate endpoints:
    - `get_authors_all` - returns all non-deleted authors without statistics
    - `load_authors_by` - optimized to use caching and efficient sorting and pagination
  - Improved SQL queries with optimized JOIN conditions and efficient filtering
  - Added pre-aggregation of statistics (shouts count, followers count) in single efficient queries
  - Implemented robust cache invalidation on author updates
  - Created necessary indexes for author lookups by user ID, slug, and timestamps

#### [0.4.14] - 2025-03-21
- Significant performance improvements for topic queries:
  - Added database indexes to optimize JOIN operations
  - Implemented persistent Redis caching for topic queries (no TTL, invalidated only on changes)
  - Optimized topic retrieval with separate endpoints for different use cases:
    - `get_topics_all` - returns all topics without statistics for lightweight listing
    - `get_topics_by_community` - adds pagination and optimized filtering by community
  - Added SQLAlchemy-managed indexes directly in ORM models for automatic schema maintenance
  - Created `sync_indexes()` function for automatic index synchronization during app startup
  - Reduced database load by pre-aggregating statistics in optimized SQL queries
  - Added robust cache invalidation on topic create/update/delete operations
  - Improved query optimization with proper JOIN conditions and specific partial indexes

#### [0.4.13] - 2025-03-20
- Fixed Topic objects serialization error in cache/memorycache.py
- Improved CustomJSONEncoder to support SQLAlchemy models with dict() method
- Enhanced error handling in cache_on_arguments decorator
- Modified `load_reactions_by` to include deleted reactions when `include_deleted=true` for proper comment tree building
- Fixed featured/unfeatured logic in reaction processing:
  - Dislike reactions now properly take precedence over likes
  - Featured status now requires more than 4 likes from users with featured articles
  - Removed unnecessary filters for deleted reactions since rating reactions are physically deleted
  - Author's featured status now based on having non-deleted articles with featured_at

#### [0.4.12] - 2025-03-19
- `delete_reaction` detects comments and uses `deleted_at` update
- `check_to_unfeature` etc. update
- dogpile dep in `services/memorycache.py` optimized

#### [0.4.11] - 2025-02-12
- `create_draft` resolver requires draft_id fixed
- `create_draft` resolver defaults body and title fields to empty string


#### [0.4.9] - 2025-02-09
- `Shout.draft` field added
- `Draft` entity added
- `create_draft`, `update_draft`, `delete_draft` mutations and resolvers added
- `create_shout`, `update_shout`, `delete_shout` mutations removed from GraphQL API
- `load_drafts` resolver implemented
- `publish_` and `unpublish_` mutations and resolvers added
- `create_`, `update_`, `delete_` mutations and resolvers added for `Draft` entity
- tests with pytest for original auth, shouts, drafts
- `Dockerfile` and `pyproject.toml` removed for the simplicity: `Procfile` and `requirements.txt`

#### [0.4.8] - 2025-02-03
- `Reaction.deleted_at` filter on `update_reaction` resolver added
- `triggers` module updated with `after_shout_handler`, `after_reaction_handler` for cache revalidation
- `after_shout_handler`, `after_reaction_handler` now also handle `deleted_at` field
- `get_cached_topic_followers` fixed
- `get_my_rates_comments` fixed

#### [0.4.7]
- `get_my_rates_shouts` resolver added with:
  - `shout_id` and `my_rate` fields in response
  - filters by `Reaction.deleted_at.is_(None)`
  - filters by `Reaction.kind.in_([ReactionKind.LIKE.value, ReactionKind.DISLIKE.value])`
  - filters by `Reaction.reply_to.is_(None)`
  - uses `local_session()` context manager
  - returns empty list on errors
- SQLAlchemy syntax updated:
  - `select()` statement fixed for newer versions
  - `Reaction` model direct selection instead of labeled columns
  - proper row access with `row[0].shout` and `row[0].kind`
- GraphQL resolver fixes:
  - added root parameter `_` to match schema
  - proper async/await handling with `@login_required`
  - error logging added via `logger.error()`

#### [0.4.6]
- login_accepted decorator added
- `docs` added
- optimized and unified `load_shouts_*` resolvers with `LoadShoutsOptions`
- `load_shouts_bookmarked` resolver fixed
- resolvers updates:
    - new resolvers group `feed`
    - `load_shouts_authored_by` resolver added
    - `load_shouts_with_topic` resolver added
    - `load_shouts_followed` removed
    - `load_shouts_random_topic` removed
    - `get_topics_random` removed
- model updates:
    - `ShoutsOrderBy` enum added
    - `Shout.main_topic` from `ShoutTopic.main` as `Topic` type output
    - `Shout.created_by` as `Author` type output

#### [0.4.5]
- `bookmark_shout` mutation resolver added
- `load_shouts_bookmarked` resolver added
- `get_communities_by_author` resolver added
- `get_communities_all` resolver fixed
- `Community` stats in orm
- `Community` CUDL resolvers added
- `Reaction` filter by `Reaction.kind`s
- `ReactionSort` enum added
- `CommunityFollowerRole` enum added
- `InviteStatus` enum added
- `Topic.parents` ids added
- `get_shout` resolver accepts slug or shout_id

#### [0.4.4]
- `followers_stat` removed for shout
- sqlite3 support added
- `rating_stat` and `commented_stat` fixes

#### [0.4.3]
- cache reimplemented
- load shouts queries unified
- `followers_stat` removed from shout

#### [0.4.2]
- reactions load resolvers separated for ratings (no stats) and comments
- reactions stats improved
- `load_comment_ratings` separate resolver

#### [0.4.1]
- follow/unfollow logic updated and unified with cache

#### [0.4.0]
- chore: version migrator synced
- feat: precache_data on start
- fix: store id list for following cache data
- fix: shouts stat filter out deleted

#### [0.3.5]
- cache isolated to services
- topics followers and authors cached
- redis stores lists of ids

#### [0.3.4]
- `load_authors_by` from cache

#### [0.3.3]
- feat: sentry integration enabled with glitchtip
- fix: reindex on update shout
- packages upgrade, isort
- separated stats queries for author and topic
- fix: feed featured filter
- fts search removed

#### [0.3.2]
- redis cache for what author follows
- redis cache for followers
- graphql add query: get topic followers

#### [0.3.1]
- enabling sentry
- long query log report added
- editor fixes
- authors links cannot be updated by `update_shout` anymore

#### [0.3.0]
- `Shout.featured_at` timestamp of the frontpage featuring event
- added proposal accepting logics
- schema modulized
- Shout.visibility removed

#### [0.2.22]
- added precommit hook
- fmt
- granian asgi

#### [0.2.21]
- fix: rating logix
- fix: `load_top_random_shouts`
- resolvers: `add_stat_*` refactored
- services: use google analytics
- services: minor fixes search

#### [0.2.20]
- services: ackee removed
- services: following manager fixed
- services: import views.json

#### [0.2.19]
- fix: adding `author` role
- fix: stripping `user_id` in auth connector

#### [0.2.18]
- schema: added `Shout.seo` string field
- resolvers: added `/new-author` webhook resolver
- resolvers: added reader.load_shouts_top_random
- resolvers: added reader.load_shouts_unrated
- resolvers: community follower id property name is `.author`
- resolvers: `get_authors_all` and `load_authors_by`
- services: auth connector upgraded

#### [0.2.17]
- schema: enum types workaround, `ReactionKind`, `InviteStatus`, `ShoutVisibility`
- schema: `Shout.created_by`, `Shout.updated_by`
- schema: `Shout.authors` can be empty
- resolvers: optimized `reacted_shouts_updates` query

#### [0.2.16]
- resolvers: collab inviting logics
- resolvers: queries and mutations revision and renaming
- resolvers: `delete_topic(slug)` implemented
- resolvers: added `get_shout_followers`
- resolvers: `load_shouts_by` filters implemented
- orm: invite entity
- schema: `Reaction.range` -> `Reaction.quote`
- filters: `time_ago` -> `after`
- httpx -> aiohttp

#### [0.2.15]
- schema: `Shout.created_by` removed
- schema: `Shout.mainTopic` removed
- services: cached elasticsearch connector
- services: auth is using `user_id` from authorizer
- resolvers: `notify_*` usage fixes
- resolvers: `getAuthor` now accepts slug, `user_id` or `author_id`
- resolvers: login_required usage fixes

#### [0.2.14]
- schema: some fixes from migrator
- schema: `.days` -> `.time_ago`
- schema: `excludeLayout` + `layout` in filters -> `layouts`
- services: db access simpler, no contextmanager
- services: removed Base.create() method
- services: rediscache updated
- resolvers: get_reacted_shouts_updates as followedReactions query

#### [0.2.13]
- services: db context manager
- services: `ViewedStorage` fixes
- services: views are not stored in core db anymore
- schema: snake case in model fields names
- schema: no DateTime scalar
- resolvers: `get_my_feed` comments filter reactions body.is_not('')
- resolvers: `get_my_feed` query fix
- resolvers: `LoadReactionsBy.days` -> `LoadReactionsBy.time_ago`
- resolvers: `LoadShoutsBy.days` -> `LoadShoutsBy.time_ago`

#### [0.2.12]
- `Author.userpic` -> `Author.pic`
- `CommunityFollower.role` is string now
- `Author.user` is string now

#### [0.2.11]
- redis interface updated
- `viewed` interface updated
- `presence` interface updated
- notify on create, update, delete for reaction and shout
- notify on follow / unfollow author
- use pyproject
- devmode fixed

#### [0.2.10]
- community resolvers connected

#### [0.2.9]
- starlette is back, aiohttp removed
- aioredis replaced with aredis

#### [0.2.8]
- refactored


#### [0.2.7]
- `loadFollowedReactions` now with `login_required`
- notifier service api draft
- added `shout` visibility kind in schema
- community isolated from author in orm


#### [0.2.6]
- redis connection pool
- auth context fixes
- communities orm, resolvers, schema


#### [0.2.5]
- restructured
- all users have their profiles as authors in core
- `gittask`, `inbox` and `auth` logics removed
- `settings` moved to base and now smaller
- new outside auth schema
- removed `gittask`, `auth`, `inbox`, `migration`
