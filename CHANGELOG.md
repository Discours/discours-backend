# Changelog

## [Unreleased]

### Изменено
- Радикально упрощена структура клиентской части приложения:
  - Удалены все избыточные файлы и директории
  - Перемещены модули auth.ts и api.ts из директории client/lib в корень директории client
  - Обновлены импорты во всех компонентах для использования модулей из корня директории
  - Создана минималистичная архитектура с 5 файлами (App, login, admin, auth, api)
  - Следование принципу DRY - устранено дублирование кода
  - Выделены общие модули для авторизации и работы с API
  - Единый стиль кода и документации для всех компонентов
  - Устранены все жесткие редиректы в пользу SolidJS Router
  - Упрощена структура проекта для лучшей поддерживаемости
- Упрощена структура клиентской части приложения:
  - Оставлены только два основных ресурса: логин и панель управления пользователями
  - Удалены избыточные компоненты и файлы
  - Упрощена логика авторизации и навигации
  - Устранены жесткие редиректы в пользу SolidJS Router
  - Созданы компактные и автономные компоненты login.tsx и admin.tsx
  - Оптимизированы стили для минимального набора компонентов

### Добавлено
- Создана панель управления пользователями в админке:
  - Добавлен компонент UsersList для управления пользователями
  - Реализованы функции блокировки/разблокировки пользователей
  - Добавлена возможность отключения звука (mute) для пользователей
  - Реализовано управление ролями пользователей через модальное окно
  - Добавлены GraphQL мутации для управления пользователями в schema/admin.graphql
  - Улучшен интерфейс админ-панели с табами для навигации
- Расширена схема GraphQL для админки:
  - Добавлены типы AdminUserInfo и AdminUserUpdateInput
  - Добавлены мутации adminUpdateUser, adminToggleUserBlock, adminToggleUserMute
  - Добавлены запросы adminGetUsers и adminGetRoles
- Пагинация списка пользователей в админ-панели
- Серверная поддержка пагинации в API для админ-панели
- Поиск пользователей по email, имени и ID
- Поддержка локального запуска сервера с HTTPS через `python run.py --https` с использованием Granian
- Интеграция с инструментом mkcert для генерации доверенных локальных SSL-сертификатов
- Поддержка запуска нескольких рабочих процессов через параметр `--workers`
- Возможность указать произвольный домен для сертификата через `--domain`

### Улучшено
- Улучшен интерфейс админ-панели:
  - Добавлены вкладки для переключения между разделами
  - Оптимизирован компонент UsersList для работы с большим количеством пользователей
  - Добавлены индикаторы статуса для заблокированных и отключенных пользователей
  - Улучшена обработка ошибок при выполнении операций с пользователями
  - Добавлены подтверждения для критичных операций (блокировка, изменение ролей)

### Полностью переработан клиентский код:
- Создан компактный API клиент с изолированным кодом для доступа к API
- Реализована модульная архитектура с четким разделением ответственности
- Добавлены типизированные интерфейсы для всех компонентов и модулей
- Реализована система маршрутизации с защищенными маршрутами
- Добавлен компонент AuthProvider для управления авторизацией
- Оптимизирована загрузка компонентов с использованием ленивой загрузки
- Унифицирован стиль кода и именования

### Исправлено
- Исправлена критическая проблема с JWT-токенами авторизации:
  - Устранена ошибка декодирования токенов `int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`
  - Обновлен механизм создания токенов для гарантированного задания срока истечения (exp)
  - Улучшена обработка ошибок в модуле аутентификации для предотвращения создания невалидных токенов
  - Стандартизован формат параметра exp в JWT: теперь всегда используется timestamp вместо datetime
  - Добавлена проверка наличия обязательных полей при декодировании токенов
  - Оптимизирована совместимость между разными способами хранения сессий
- Исправлена проблема с перенаправлением в SolidJS, которое сбрасывало состояние приложения:
  - Обновлена функция logout для использования колбэка навигации вместо жесткого редиректа
  - Добавлен компонент LoginPage для авторизации без перезагрузки страницы
  - Реализована ленивая загрузка компонентов с использованием Suspense
  - Улучшена структура роутинга в админ-панели
  - Оптимизирован код согласно принципам DRY и KISS

### Улучшения для авторизации в админ-панели

- Исправлена проблема с авторизацией в админ-панели
- Добавлена поддержка httpOnly cookies для безопасного хранения токена авторизации
- Реализован механизм выхода из системы через отзыв токенов
- Добавлен компонент для отображения списка пользователей в админке
- Добавлена постраничная навигация между управлением переменными окружения и списком пользователей
- Улучшена обработка сессий в API GraphQL

### Исправлено
- Переработан резолвер login_mutation для соответствия общему стилю других мутаций в кодбазе
- Реализована корректная обработка логина через `AuthResult`, устранена ошибка GraphQL "Cannot return null for non-nullable field Mutation.login"
- Улучшена обработка ошибок в модуле авторизации:
  - Добавлена проверка корректности объекта автора перед созданием токена
  - Исправлен порядок импорта резолверов для корректной регистрации обработчиков
  - Добавлено расширенное логирование для отладки авторизации
  - Гарантирован непустой возврат из резолвера login для предотвращения GraphQL ошибки
- Исправлена ошибка "Author password is empty" при авторизации:
  - Добавлено поле password в метод dict() класса Author для корректной передачи при создании экземпляра из словаря
- Устранена ошибка `Author object has no attribute username` при создании токена авторизации:
  - Добавлено свойство username в класс Author для совместимости с `TokenStorage`
- Исправлена HTML-форма на странице входа в админ-панель:
  - Добавлен тег `<form>` для устранения предупреждения браузера о полях пароля вне формы
  - Улучшена доступность и UX формы логина
  - Добавлены атрибуты `autocomplete` для улучшения работы с менеджерами паролей
  - Внедрена более строгая валидация полей и фокусировка на ошибках

### Added
- Подробная документация модуля аутентификации в `docs/auth.md`
- Система ролей и разрешений (RBAC)
- Защита от брутфорс атак
- Мультиязычная поддержка в email уведомлениях
- Подробная документация по системе авторизации в `docs/auth.md`
  - Описание OAuth интеграции
  - Руководство по RBAC
  - Примеры использования на фронтенде
  - Инструкции по безопасности
  - Документация по тестированию
- Страница входа для неавторизованных пользователей в админке
- Публичное GraphQL API для модуля аутентификации:
  - Типы: `AuthResult`, `Permission`, `SessionInfo`, `OAuthProvider`
  - Мутации: `login`, `registerUser`, `sendLink`, `confirmEmail`, `getSession`, `changePassword`, `refreshToken`
  - Запросы: `logout`, `me`, `isEmailUsed`, `getOAuthProviders`

### Changed
- Переработана структура модуля auth для лучшей модульности
- Улучшена обработка ошибок в auth endpoints
- Оптимизировано хранение сессий в Redis
- Усилена безопасность хеширования паролей
- Удалена поддержка удаленной аутентификации в пользу единой локальной системы аутентификации
  - Удалены настройки `AUTH_MODE` и `AUTH_URL`
  - Удалены зависимости от внешнего сервиса авторизации
  - Упрощен код аутентификации
- Консолидация типов для авторизации: 
  - Удален дублирующий тип `UserInfo`
  - Расширен тип `Author` полями для работы с авторизацией (`roles`, `email_verified`)
  - Использование единого типа `Author` во всех запросах авторизации

### Fixed
- Исправлена проблема с кэшированием разрешений
- Улучшена валидация email и username
- Исправлена обработка истекших токенов
- Исправлена ошибка в функции `get_with_stat` в модуле resolvers/stat.py: добавлен вызов метода `.unique()` для результатов запросов с joined eager loads
- Исправлены ошибки в декораторах auth:
  - Добавлены проверки на None для объекта `info` в декораторах `admin_auth_required` и `require_permission`
  - Улучшена обработка ошибок в GraphQL контексте
- Добавлен AuthenticationMiddleware с использованием InternalAuthentication для работы с request.auth
- Исправлена ошибка с классом InternalAuthentication: 
  - Добавлен класс AuthenticatedUser
  - Реализован корректный возврат кортежа (AuthCredentials, BaseUser) из метода authenticate

#### [0.4.21] - 2023-09-10

### Изменено
- Переработана пагинация в админ-панели: переход с модели page/perPage на limit/offset
- Улучшена производительность при работе с большими списками пользователей
- Оптимизирован GraphQL API для управления пользователями

### Исправлено
- Исправлена ошибка GraphQL "Unknown argument 'page' on field 'Query.adminGetUsers'"
- Согласованы параметры пагинации между клиентом и сервером

#### [0.4.20] - 2023-09-01

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
- `rating_stat` and `comments_count` fixes

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
- `loadFollowedReactions` now with `