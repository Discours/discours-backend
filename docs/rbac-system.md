# Система RBAC (Role-Based Access Control)

## Обзор

Система управления доступом на основе ролей для платформы Discours. Роли хранятся в CSV формате в таблице `CommunityAuthor` и могут быть назначены пользователям в рамках конкретного сообщества.

> **v0.6.11: Важно!** Наследование разрешений между ролями происходит **только при инициализации** прав для сообщества. В Redis хранятся уже развернутые (полные) списки разрешений для каждой роли. При запросе прав никакого on-the-fly наследования не происходит — только lookup по роли.

## Архитектура

### Основные принципы
- **CSV хранение**: Роли хранятся как CSV строка в поле `roles` таблицы `CommunityAuthor`
- **Простота**: Один пользователь может иметь несколько ролей в одном сообществе
- **Привязка к сообществу**: Роли существуют в контексте конкретного сообщества
- **Иерархия ролей**: `reader` → `author` → `artist` → `expert` → `editor` → `admin`
- **Наследование прав**: Каждая роль наследует все права предыдущих ролей **только при инициализации**

### Схема базы данных

#### Таблица `community_author`
```sql
CREATE TABLE community_author (
    id INTEGER PRIMARY KEY,
    community_id INTEGER REFERENCES community(id) NOT NULL,
    author_id INTEGER REFERENCES author(id) NOT NULL,
    roles TEXT,                         -- CSV строка ролей ("reader,author,expert")
    joined_at INTEGER NOT NULL,         -- Unix timestamp присоединения

    CONSTRAINT uq_community_author UNIQUE (community_id, author_id)
);
```

#### Индексы
```sql
CREATE INDEX idx_community_author_community ON community_author(community_id);
CREATE INDEX idx_community_author_author ON community_author(author_id);
```

## Работа с ролями

### Модель CommunityAuthor

#### Основные методы
```python
from orm.community import CommunityAuthor

# Получение списка ролей
ca = session.query(CommunityAuthor).first()
roles = ca.role_list  # ['reader', 'author', 'expert']

# Установка ролей
ca.role_list = ['reader', 'author']

# Проверка роли
has_author = ca.has_role('author')  # True

# Добавление роли
ca.add_role('expert')

# Удаление роли
ca.remove_role('author')

# Установка полного списка ролей
ca.set_roles(['reader', 'editor'])

# Получение всех разрешений
permissions = await ca.get_permissions()  # ['shout:read', 'shout:create', ...]

# Проверка разрешения
can_create = await ca.has_permission('shout:create')  # True
```

### Вспомогательные функции

#### Основные функции из `orm/community.py`
```python
from orm.community import (
    get_user_roles_in_community,
    check_user_permission_in_community,
    assign_role_to_user,
    remove_role_from_user,
    get_all_community_members_with_roles,
    bulk_assign_roles
)

# Получение ролей пользователя
roles = get_user_roles_in_community(author_id=123, community_id=1)
# Возвращает: ['reader', 'author']

# Проверка разрешения
has_perm = await check_user_permission_in_community(
    author_id=123,
    permission='shout:create',
    community_id=1
)

# Назначение роли
success = assign_role_to_user(
    author_id=123,
    role='expert',
    community_id=1
)

# Удаление роли
success = remove_role_from_user(
    author_id=123,
    role='author',
    community_id=1
)

# Получение всех участников с ролями
members = get_all_community_members_with_roles(community_id=1)
# Возвращает: [{'author_id': 123, 'roles': ['reader', 'author'], ...}, ...]

# Массовое назначение ролей
bulk_assign_roles([
    {'author_id': 123, 'roles': ['reader', 'author']},
    {'author_id': 456, 'roles': ['expert', 'editor']}
], community_id=1)
```

## Система разрешений

### Иерархия ролей
```
reader → author → artist → expert → editor → admin
```

Каждая роль наследует все права предыдущих ролей в дефолтной иерархии **только при создании сообщества**.

### Стандартные роли и их права

| Роль | Базовые права | Дополнительные права |
|------|---------------|---------------------|
| `reader` | `*:read`, базовые реакции | `chat:*`, `message:*` |
| `author` | Наследует `reader` + `*:create`, `*:update_own`, `*:delete_own` | `draft:*` |
| `artist` | Наследует `author` | `reaction:CREDIT:accept`, `reaction:CREDIT:decline` |
| `expert` | Наследует `author` | `reaction:PROOF:*`, `reaction:DISPROOF:*`, `reaction:AGREE:*`, `reaction:DISAGREE:*` |
| `editor` | `*:read`, `*:create`, `*:update_any`, `*:delete_any` | `community:read`, `community:update_own` |
| `admin` | Все права (`*`) | Полный доступ ко всем функциям |

### Формат разрешений
- Базовые: `<entity>:<action>` (например: `shout:create`)
- Реакции: `reaction:<type>:<action>` (например: `reaction:LIKE:create`)
- Wildcard: `<entity>:*` или `*` (только для admin)

## GraphQL API

### Запросы

#### Получение участников сообщества с ролями
```graphql
query AdminGetCommunityMembers(
    $community_id: Int!
    $page: Int = 1
    $limit: Int = 50
) {
    adminGetCommunityMembers(
        community_id: $community_id
        page: $page
        limit: $limit
    ) {
        success
        error
        members {
            id
            name
            slug
            email
            roles
            is_follower
            created_at
        }
        total
        page
        limit
        has_next
    }
}
```

### Мутации

#### Назначение ролей пользователю
```graphql
mutation AdminSetUserCommunityRoles(
    $author_id: Int!
    $community_id: Int!
    $roles: [String!]!
) {
    adminSetUserCommunityRoles(
        author_id: $author_id
        community_id: $community_id
        roles: $roles
    ) {
        success
        error
        author_id
        community_id
        roles
    }
}
```

#### Обновление настроек ролей сообщества
```graphql
mutation AdminUpdateCommunityRoleSettings(
    $community_id: Int!
    $default_roles: [String!]!
    $available_roles: [String!]!
) {
    adminUpdateCommunityRoleSettings(
        community_id: $community_id
        default_roles: $default_roles
        available_roles: $available_roles
    ) {
        success
        error
        community_id
        default_roles
        available_roles
    }
}
```

## Использование декораторов RBAC

### Импорт декораторов
```python
from resolvers.rbac import (
    require_permission, require_role, admin_only,
    authenticated_only, require_any_permission,
    require_all_permissions, RBACError
)
```

### Примеры использования

#### Проверка конкретного разрешения
```python
@mutation.field("createShout")
@require_permission("shout:create")
async def create_shout(self, info: GraphQLResolveInfo, **kwargs):
    # Только пользователи с правом создания статей
    return await self._create_shout_logic(**kwargs)
```

#### Проверка любого из разрешений (OR логика)
```python
@mutation.field("updateShout")
@require_any_permission(["shout:update_own", "shout:update_any"])
async def update_shout(self, info: GraphQLResolveInfo, shout_id: int, **kwargs):
    # Может редактировать свои статьи ИЛИ любые статьи
    return await self._update_shout_logic(shout_id, **kwargs)
```

#### Проверка конкретной роли
```python
@mutation.field("verifyEvidence")
@require_role("expert")
async def verify_evidence(self, info: GraphQLResolveInfo, **kwargs):
    # Только эксперты могут верифицировать доказательства
    return await self._verify_evidence_logic(**kwargs)
```

#### Только для администраторов
```python
@mutation.field("deleteAnyContent")
@admin_only
async def delete_any_content(self, info: GraphQLResolveInfo, content_id: int):
    # Только администраторы
    return await self._delete_content_logic(content_id)
```

### Обработка ошибок
```python
from resolvers.rbac import RBACError

try:
    result = await some_rbac_protected_function()
except RBACError as e:
    return {"success": False, "error": str(e)}
```

## Настройка сообщества

### Управление ролями в сообществе
```python
from orm.community import Community

community = session.query(Community).filter(Community.id == 1).first()

# Установка доступных ролей
community.set_available_roles(['reader', 'author', 'expert', 'admin'])

# Установка дефолтных ролей для новых участников
community.set_default_roles(['reader'])

# Получение настроек
available = community.get_available_roles()  # ['reader', 'author', 'expert', 'admin']
default = community.get_default_roles()      # ['reader']
```

### Автоматическое назначение дефолтных ролей
При создании связи пользователя с сообществом автоматически назначаются роли из `default_roles`.

## Интеграция с GraphQL контекстом

### Middleware для установки ролей
```python
async def rbac_middleware(request, call_next):
    # Получаем автора из контекста
    author = getattr(request.state, 'author', None)
    if author:
        # Устанавливаем роли в контекст для текущего сообщества
        community_id = get_current_community_id(request)
        if community_id:
            user_roles = get_user_roles_in_community(author.id, community_id)
            request.state.user_roles = user_roles

    response = await call_next(request)
    return response
```

### Получение ролей в resolver'ах
```python
def get_user_roles_from_context(info):
    """Получение ролей пользователя из GraphQL контекста"""
    # Из middleware
    user_roles = getattr(info.context, "user_roles", [])
    if user_roles:
        return user_roles

    # Из author'а напрямую
    author = getattr(info.context, "author", None)
    if author and hasattr(author, "roles"):
        return author.roles.split(",") if author.roles else []

    return []
```

## Миграция и обновления

### Миграция с предыдущей системы ролей
Если в проекте была отдельная таблица ролей, необходимо:

1. Создать миграцию для добавления поля `roles` в `CommunityAuthor`
2. Перенести данные из старых таблиц в CSV формат
3. Удалить старые таблицы ролей

```bash
alembic revision --autogenerate -m "Add CSV roles to CommunityAuthor"
alembic upgrade head
```

### Обновление CHANGELOG.md
После внесения изменений в RBAC систему обновляется `CHANGELOG.md` с новой версией.

## Производительность

### Оптимизация
- CSV роли хранятся в одном поле, что снижает количество JOIN'ов
- Индексы на `community_id` и `author_id` ускоряют запросы
- Кеширование разрешений на уровне приложения

### Рекомендации
- Избегать частых изменений ролей
- Кешировать результаты `get_role_permissions_for_community()`
- Использовать bulk операции для массового назначения ролей
