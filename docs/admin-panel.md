# Администраторская панель Discours

## Обзор

Администраторская панель — это комплексная система управления платформой Discours, предоставляющая полный контроль над пользователями, публикациями, сообществами и их ролями.

## Архитектура системы доступа

### Уровни доступа

1. **Системные администраторы** — email в переменной `ADMIN_EMAILS` (управление системой через переменные среды)
2. **RBAC роли в сообществах** — `reader`, `author`, `artist`, `expert`, `editor`, `admin` (управляемые через админку)

**ВАЖНО**:
- Роль `admin` в RBAC — это обычная роль в сообществе, управляемая через админку
- "Системный администратор" — синтетическая роль, которая НЕ хранится в базе данных
- Синтетическая роль добавляется только в API ответы для пользователей из `ADMIN_EMAILS`
- На фронте в сообществах синтетическая роль НЕ отображается

### Декораторы безопасности

```python
@admin_auth_required  # Доступ только системным админам (ADMIN_EMAILS)
@editor_or_admin_required  # Доступ редакторам и админам сообщества (RBAC роли)
```

## Модули администрирования

### 1. Управление пользователями

#### Получение списка пользователей
```graphql
query AdminGetUsers(
    $limit: Int = 20
    $offset: Int = 0
    $search: String = ""
) {
    adminGetUsers(limit: $limit, offset: $offset, search: $search) {
        authors {
            id
            email
            name
            slug
            roles
            created_at
            last_seen
        }
        total
        page
        perPage
        totalPages
    }
}
```

**Особенности:**
- Поиск по email, имени и ID
- Пагинация с ограничением 1-100 записей
- Роли получаются из основного сообщества (ID=1)
- Автоматическое добавление синтетической роли "Системный администратор" для email из `ADMIN_EMAILS`

#### Обновление пользователя
```graphql
mutation AdminUpdateUser($user: AdminUserUpdateInput!) {
    adminUpdateUser(user: $user) {
        success
        error
    }
}
```

**Поддерживаемые поля:**
- `email` — с проверкой уникальности
- `name` — имя пользователя
- `slug` — с проверкой уникальности
- `roles` — массив ролей для основного сообщества

### 2. Система ролей и разрешений (RBAC)

#### Иерархия ролей
```
reader → author → artist → expert → editor → admin
```

Каждая роль наследует права предыдущих **только при инициализации** сообщества.

#### Получение ролей
```graphql
query AdminGetRoles($community: Int) {
    adminGetRoles(community: $community) {
        id
        name
        description
    }
}
```

- Без `community` — все системные роли
- С `community` — роли конкретного сообщества + счетчик разрешений

#### Управление ролями в сообществах

**Получение ролей пользователя:**
```graphql
query AdminGetUserCommunityRoles(
    $author_id: Int!
    $community_id: Int!
) {
    adminGetUserCommunityRoles(
        author_id: $author_id
        community_id: $community_id
    ) {
        author_id
        community_id
        roles
    }
}
```

**Назначение ролей:**
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

**Добавление отдельной роли:**
```graphql
mutation AdminAddUserToRole(
    $author_id: Int!
    $role_id: String!
    $community_id: Int!
) {
    adminAddUserToRole(
        author_id: $author_id
        role_id: $role_id
        community_id: $community_id
    ) {
        success
        error
    }
}
```

**Удаление роли:**
```graphql
mutation AdminRemoveUserFromRole(
    $author_id: Int!
    $role_id: String!
    $community_id: Int!
) {
    adminRemoveUserFromRole(
        author_id: $author_id
        role_id: $role_id
        community_id: $community_id
    ) {
        success
        removed
    }
}
```

### 3. Управление сообществами

#### Участники сообщества
```graphql
query AdminGetCommunityMembers(
    $community_id: Int!
    $limit: Int = 20
    $offset: Int = 0
) {
    adminGetCommunityMembers(
        community_id: $community_id
        limit: $limit
        offset: $offset
    ) {
        members {
            id
            name
            email
            slug
            roles
        }
        total
        community_id
    }
}
```

#### Настройки ролей сообщества

**Получение настроек:**
```graphql
query AdminGetCommunityRoleSettings($community_id: Int!) {
    adminGetCommunityRoleSettings(community_id: $community_id) {
        community_id
        default_roles
        available_roles
        error
    }
}
```

**Обновление настроек:**
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

#### Создание пользовательской роли
```graphql
mutation AdminCreateCustomRole($role: CustomRoleInput!) {
    adminCreateCustomRole(role: $role) {
        success
        error
        role {
            id
            name
            description
        }
    }
}
```

#### Удаление пользовательской роли
```graphql
mutation AdminDeleteCustomRole(
    $role_id: String!
    $community_id: Int!
) {
    adminDeleteCustomRole(
        role_id: $role_id
        community_id: $community_id
    ) {
        success
        error
    }
}
```

### 4. Управление публикациями

#### Получение списка публикаций
```graphql
query AdminGetShouts(
    $limit: Int = 20
    $offset: Int = 0
    $search: String = ""
    $status: String = "all"
    $community: Int
) {
    adminGetShouts(
        limit: $limit
        offset: $offset
        search: $search
        status: $status
        community: $community
    ) {
        shouts {
            id
            title
            slug
            body
            lead
            subtitle
            # ... остальные поля
            created_by {
                id
                email
                name
                slug
            }
            community {
                id
                name
                slug
            }
            authors {
                id
                email
                name
                slug
            }
            topics {
                id
                title
                slug
            }
        }
        total
        page
        perPage
        totalPages
    }
}
```

**Статусы публикаций:**
- `all` — все публикации (включая удаленные)
- `published` — опубликованные
- `draft` — черновики
- `deleted` — удаленные

#### Операции с публикациями

**Обновление:**
```graphql
mutation AdminUpdateShout($shout: AdminShoutUpdateInput!) {
    adminUpdateShout(shout: $shout) {
        success
        error
    }
}
```

**Удаление (мягкое):**
```graphql
mutation AdminDeleteShout($shout_id: Int!) {
    adminDeleteShout(shout_id: $shout_id) {
        success
        error
    }
}
```

**Восстановление:**
```graphql
mutation AdminRestoreShout($shout_id: Int!) {
    adminRestoreShout(shout_id: $shout_id) {
        success
        error
    }
}
```

### 5. Управление приглашениями

#### Получение списка приглашений
```graphql
query AdminGetInvites(
    $limit: Int = 20
    $offset: Int = 0
    $search: String = ""
    $status: String = "all"
) {
    adminGetInvites(
        limit: $limit
        offset: $offset
        search: $search
        status: $status
    ) {
        invites {
            inviter_id
            author_id
            shout_id
            status
            inviter {
                id
                email
                name
                slug
            }
            author {
                id
                email
                name
                slug
            }
            shout {
                id
                title
                slug
                created_by {
                    id
                    email
                    name
                    slug
                }
            }
        }
        total
        page
        perPage
        totalPages
    }
}
```

**Статусы приглашений:**
- `PENDING` — ожидает ответа
- `ACCEPTED` — принято
- `REJECTED` — отклонено

#### Операции с приглашениями

**Обновление статуса:**
```graphql
mutation AdminUpdateInvite($invite: AdminInviteUpdateInput!) {
    adminUpdateInvite(invite: $invite) {
        success
        error
    }
}
```

**Удаление:**
```graphql
mutation AdminDeleteInvite(
    $inviter_id: Int!
    $author_id: Int!
    $shout_id: Int!
) {
    adminDeleteInvite(
        inviter_id: $inviter_id
        author_id: $author_id
        shout_id: $shout_id
    ) {
        success
        error
    }
}
```

**Пакетное удаление:**
```graphql
mutation AdminDeleteInvitesBatch($invites: [AdminInviteIdInput!]!) {
    adminDeleteInvitesBatch(invites: $invites) {
        success
        error
    }
}
```

### 6. Переменные окружения

Системные администраторы могут управлять переменными окружения:

```graphql
query GetEnvVariables {
    getEnvVariables {
        name
        description
        variables {
            key
            value
            description
            type
            isSecret
        }
    }
}
```

```graphql
mutation UpdateEnvVariable($key: String!, $value: String!) {
    updateEnvVariable(key: $key, value: $value) {
        success
        error
    }
}
```

## Особенности реализации

### Принцип DRY
- Переиспользование логики из `reader.py`, `editor.py`
- Общие утилиты в `_get_user_roles()`
- Централизованная обработка ошибок

### Новая RBAC система
- Роли хранятся в CSV формате в `CommunityAuthor.roles`
- Методы модели: `add_role()`, `remove_role()`, `set_roles()`, `has_role()`
- Права наследуются **только при инициализации**
- Redis кэширование развернутых прав

### Синтетические роли
- **"Системный администратор"** — добавляется автоматически для пользователей из `ADMIN_EMAILS`
- НЕ хранится в базе данных, только в API ответах
- НЕ отображается на фронте в интерфейсах управления сообществами
- Используется только для индикации системных прав доступа

### Безопасность
- Валидация всех входных данных
- Проверка существования сущностей
- Контроль доступа через декораторы
- Логирование всех административных действий

### Производительность
- Пагинация для всех списков
- Индексы по ключевым полям
- Ограничения на размер выборки (max 100)
- Оптимизированные SQL запросы с `joinedload`

## Миграция данных

При переходе на новую RBAC систему используется функция:

```python
from orm.community import migrate_old_roles_to_community_author
migrate_old_roles_to_community_author()
```

Функция автоматически переносит роли из старых таблиц в новый формат CSV.

## Мониторинг и логирование

Все административные действия логируются с уровнем INFO:
- Изменение ролей пользователей
- Обновление настроек сообществ
- Операции с публикациями
- Управление приглашениями

Ошибки логируются с уровнем ERROR и полным стектрейсом.

## Лучшие практики

1. **Всегда проверяйте роли перед назначением**
2. **Используйте транзакции для групповых операций**
3. **Логируйте критические изменения**
4. **Валидируйте права доступа на каждом этапе**
5. **Применяйте принцип минимальных привилегий**

## Расширение функциональности

Для добавления новых административных функций:

1. Создайте резолвер с соответствующим декоратором
2. Добавьте GraphQL схему в `schema/admin.graphql`
3. Реализуйте логику с переиспользованием существующих компонентов
4. Добавьте тесты и документацию
5. Обновите права доступа при необходимости
