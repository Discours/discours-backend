# Система ролей и разрешений (RBAC)

## Общее описание

Система управления доступом на основе ролей (Role-Based Access Control, RBAC) обеспечивает гибкое управление правами пользователей в рамках сообществ платформы.

## Архитектура системы

### Основные компоненты

1. **Community** - сообщество, контекст для ролей
2. **CommunityAuthor** - связь пользователя с сообществом и его ролями
3. **Role** - роль пользователя (reader, author, editor, admin)
4. **Permission** - разрешение на выполнение действия
5. **RBAC Service** - сервис управления ролями и разрешениями

### Модель данных

```sql
-- Основная таблица связи пользователя с сообществом
CREATE TABLE community_author (
    id INTEGER PRIMARY KEY,
    community_id INTEGER REFERENCES community(id),
    author_id INTEGER REFERENCES author(id),
    roles TEXT, -- CSV строка ролей: "reader,author,editor"
    joined_at INTEGER NOT NULL,
    UNIQUE(community_id, author_id)
);

-- Индексы для производительности
CREATE INDEX idx_community_author_community ON community_author(community_id);
CREATE INDEX idx_community_author_author ON community_author(author_id);
```

## Роли в системе

### Базовые роли

#### 1. `reader` (Читатель)
- **Обязательная роль для всех пользователей**
- **Права:**
  - Чтение публикаций
  - Просмотр комментариев
  - Подписка на сообщества
  - Базовая навигация по платформе

#### 2. `author` (Автор)
- **Права:**
  - Все права `reader`
  - Создание публикаций (шаутов)
  - Редактирование своих публикаций
  - Комментирование
  - Создание черновиков

#### 3. `artist` (Художник)
- **Права:**
  - Все права `author`
  - Может быть указан как credited artist
  - Загрузка и управление медиафайлами

#### 4. `expert` (Эксперт)
- **Права:**
  - Все права `author`
  - Добавление доказательств (evidence)
  - Верификация контента
  - Экспертная оценка публикаций

#### 5. `editor` (Редактор)
- **Права:**
  - Все права `expert`
  - Модерация контента
  - Редактирование чужих публикаций
  - Управление тегами и категориями
  - Модерация комментариев

#### 6. `admin` (Администратор)
- **Права:**
  - Все права `editor`
  - Управление пользователями
  - Управление ролями
  - Настройка сообщества
  - Полный доступ к административной панели

### Иерархия ролей

```
admin > editor > expert > artist/author > reader
```

Каждая роль автоматически включает права всех ролей ниже по иерархии.

## Разрешения (Permissions)

### Формат разрешений

Разрешения записываются в формате `resource:action`:

- `shout:create` - создание публикаций
- `shout:edit` - редактирование публикаций
- `shout:delete` - удаление публикаций
- `comment:create` - создание комментариев
- `comment:moderate` - модерация комментариев
- `user:manage` - управление пользователями
- `community:settings` - настройки сообщества

### Категории разрешений

#### Контент (Content)
- `shout:create` - создание шаутов
- `shout:edit_own` - редактирование своих шаутов
- `shout:edit_any` - редактирование любых шаутов
- `shout:delete_own` - удаление своих шаутов
- `shout:delete_any` - удаление любых шаутов
- `shout:publish` - публикация шаутов
- `shout:feature` - продвижение шаутов

#### Комментарии (Comments)
- `comment:create` - создание комментариев
- `comment:edit_own` - редактирование своих комментариев
- `comment:edit_any` - редактирование любых комментариев
- `comment:delete_own` - удаление своих комментариев
- `comment:delete_any` - удаление любых комментариев
- `comment:moderate` - модерация комментариев

#### Пользователи (Users)
- `user:view_profile` - просмотр профилей
- `user:edit_own_profile` - редактирование своего профиля
- `user:manage_roles` - управление ролями пользователей
- `user:ban` - блокировка пользователей

#### Сообщество (Community)
- `community:view` - просмотр сообщества
- `community:settings` - настройки сообщества
- `community:manage_members` - управление участниками
- `community:analytics` - просмотр аналитики

## Логика работы системы

### 1. Регистрация пользователя

При регистрации пользователя:

```python
# 1. Создается запись в Author
user = Author(email=email, name=name, ...)

# 2. Создается связь с дефолтным сообществом (ID=1)
community_author = CommunityAuthor(
    community_id=1,
    author_id=user.id,
    roles="reader,author"  # Дефолтные роли
)

# 3. Создается подписка на сообщество
follower = CommunityFollower(
    community=1,
    follower=user.id
)
```

### 2. Проверка авторизации

При входе в систему проверяется наличие роли `reader`:

```python
def login(email, password):
    # 1. Найти пользователя
    author = Author.get_by_email(email)

    # 2. Проверить пароль
    if not verify_password(password, author.password):
        return error("Неверный пароль")

    # 3. Получить роли в дефолтном сообществе
    user_roles = get_user_roles_in_community(author.id, community_id=1)

    # 4. Проверить наличие роли reader
    if "reader" not in user_roles and author.email not in ADMIN_EMAILS:
        return error("Нет прав для входа. Требуется роль 'reader'.")

    # 5. Создать сессию
    return create_session(author)
```

### 3. Проверка разрешений

При выполнении действий проверяются разрешения:

```python
@login_required
async def create_shout(info, input):
    user_id = info.context["author"]["id"]

    # Проверяем разрешение на создание шаутов
    has_permission = await check_user_permission_in_community(
        user_id,
        "shout:create",
        community_id=1
    )

    if not has_permission:
        raise GraphQLError("Недостаточно прав для создания публикации")

    # Создаем шаут
    return Shout.create(input)
```

### 4. Управление ролями

#### Назначение ролей

```python
# Назначить роль пользователю
assign_role_to_user(user_id=123, role="editor", community_id=1)

# Убрать роль
remove_role_from_user(user_id=123, role="editor", community_id=1)

# Установить все роли
community.set_user_roles(user_id=123, roles=["reader", "author", "editor"])
```

#### Проверка ролей

```python
# Получить роли пользователя
roles = get_user_roles_in_community(user_id=123, community_id=1)

# Проверить конкретную роль
has_role = "editor" in roles

# Проверить разрешение
has_permission = await check_user_permission_in_community(
    user_id=123,
    permission="shout:edit_any",
    community_id=1
)
```

## Конфигурация сообщества

### Дефолтные роли

Каждое сообщество может настроить свои дефолтные роли для новых пользователей:

```python
# Получить дефолтные роли
default_roles = community.get_default_roles()  # ["reader", "author"]

# Установить дефолтные роли
community.set_default_roles(["reader"])  # Только reader по умолчанию
```

### Доступные роли

Сообщество может ограничить список доступных ролей:

```python
# Все роли доступны по умолчанию
available_roles = ["reader", "author", "artist", "expert", "editor", "admin"]

# Ограничить только базовыми ролями
community.set_available_roles(["reader", "author", "editor"])
```

## Миграция данных

### Проблемы существующих пользователей

1. **Пользователи без роли `reader`** - не могут войти в систему
2. **Старая система ролей** - данные в `Author.roles` устарели
3. **Отсутствие связей `CommunityAuthor`** - новые пользователи без ролей

### Решения

#### 1. Автоматическое добавление роли `reader`

```python
async def ensure_user_has_reader_role(user_id: int) -> bool:
    """Убеждается, что у пользователя есть роль 'reader'"""
    existing_roles = get_user_roles_in_community(user_id, community_id=1)

    if "reader" not in existing_roles:
        success = assign_role_to_user(user_id, "reader", community_id=1)
        if success:
            logger.info(f"Роль 'reader' добавлена пользователю {user_id}")
            return True

    return True
```

#### 2. Массовое исправление ролей

```python
async def fix_all_users_reader_role() -> dict[str, int]:
    """Проверяет всех пользователей и добавляет роль 'reader'"""
    stats = {"checked": 0, "fixed": 0, "errors": 0}

    all_authors = session.query(Author).all()

    for author in all_authors:
        stats["checked"] += 1
        try:
            await ensure_user_has_reader_role(author.id)
            stats["fixed"] += 1
        except Exception as e:
            logger.error(f"Ошибка для пользователя {author.id}: {e}")
            stats["errors"] += 1

    return stats
```

#### 3. Миграция из старой системы

```python
def migrate_old_roles_to_community_author():
    """Переносит роли из старой системы в CommunityAuthor"""

    # Получаем все старые роли из Author.roles
    old_roles = session.query(AuthorRole).all()

    for role in old_roles:
        # Создаем запись CommunityAuthor
        ca = CommunityAuthor(
            community_id=role.community,
            author_id=role.author,
            roles=role.role
        )
        session.add(ca)

    session.commit()
```

## API для работы с ролями

### GraphQL мутации

```graphql
# Назначить роль пользователю
mutation AssignRole($userId: Int!, $role: String!, $communityId: Int) {
    assignRole(userId: $userId, role: $role, communityId: $communityId) {
        success
        message
    }
}

# Убрать роль
mutation RemoveRole($userId: Int!, $role: String!, $communityId: Int) {
    removeRole(userId: $userId, role: $role, communityId: $communityId) {
        success
        message
    }
}

# Установить все роли пользователя
mutation SetUserRoles($userId: Int!, $roles: [String!]!, $communityId: Int) {
    setUserRoles(userId: $userId, roles: $roles, communityId: $communityId) {
        success
        message
    }
}
```

### GraphQL запросы

```graphql
# Получить роли пользователя
query GetUserRoles($userId: Int!, $communityId: Int) {
    userRoles(userId: $userId, communityId: $communityId) {
        roles
        permissions
        community {
            id
            name
        }
    }
}

# Получить всех участников сообщества с ролями
query GetCommunityMembers($communityId: Int!) {
    communityMembers(communityId: $communityId) {
        authorId
        roles
        permissions
        joinedAt
        author {
            id
            name
            email
        }
    }
}
```

## Безопасность

### Принципы безопасности

1. **Принцип минимальных привилегий** - пользователь получает только необходимые права
2. **Разделение обязанностей** - разные роли для разных функций
3. **Аудит действий** - логирование всех изменений ролей
4. **Проверка на каждом уровне** - валидация разрешений в API и UI

### Защита от атак

1. **Privilege Escalation** - проверка прав на изменение ролей
2. **Mass Assignment** - валидация входных данных
3. **CSRF** - использование токенов для изменения ролей
4. **XSS** - экранирование данных ролей в UI

### Логирование

```python
# Логирование изменений ролей
logger.info(f"Role {role} assigned to user {user_id} by admin {admin_id}")
logger.warning(f"Failed login attempt for user without reader role: {user_id}")
logger.error(f"Permission denied: user {user_id} tried to access {resource}")
```

## Тестирование

### Тестовые сценарии

1. **Регистрация пользователя** - проверка назначения дефолтных ролей
2. **Вход в систему** - проверка требования роли `reader`
3. **Назначение ролей** - проверка прав администратора
4. **Проверка разрешений** - валидация доступа к ресурсам
5. **Иерархия ролей** - наследование прав

### Пример тестов

```python
def test_user_registration_assigns_default_roles():
    """Проверяет назначение дефолтных ролей при регистрации"""
    user = create_user(email="test@test.com")
    roles = get_user_roles_in_community(user.id, community_id=1)

    assert "reader" in roles
    assert "author" in roles

def test_login_requires_reader_role():
    """Проверяет требование роли reader для входа"""
    user = create_user_without_roles(email="test@test.com")

    result = login(email="test@test.com", password="password")

    assert result["success"] == False
    assert "reader" in result["error"]

def test_role_hierarchy():
    """Проверяет иерархию ролей"""
    user = create_user(email="admin@test.com")
    assign_role_to_user(user.id, "admin", community_id=1)

    # Админ должен иметь все права
    assert check_permission(user.id, "shout:create")
    assert check_permission(user.id, "user:manage")
    assert check_permission(user.id, "community:settings")
```

## Производительность

### Оптимизации

1. **Кеширование ролей** - хранение ролей пользователя в Redis
2. **Индексы БД** - быстрый поиск по `community_id` и `author_id`
3. **Batch операции** - массовое назначение ролей
4. **Ленивая загрузка** - загрузка разрешений по требованию

### Мониторинг

```python
# Метрики для Prometheus
role_checks_total = Counter('rbac_role_checks_total')
permission_checks_total = Counter('rbac_permission_checks_total')
role_assignments_total = Counter('rbac_role_assignments_total')
```
