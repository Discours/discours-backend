# Модуль аутентификации и авторизации

## Общее описание

Модуль реализует полноценную систему аутентификации с использованием локальной БД и Redis.

## Компоненты

### Модели данных

#### Author (orm.py)
- Основная модель пользователя с расширенным функционалом аутентификации
- Поддерживает:
  - Локальную аутентификацию по email/телефону
  - Систему ролей и разрешений (RBAC)
  - Блокировку аккаунта при множественных неудачных попытках входа
  - Верификацию email/телефона

#### Role и Permission (orm.py)
- Реализация RBAC (Role-Based Access Control)
- Роли содержат наборы разрешений
- Разрешения определяются как пары resource:operation

### Аутентификация

#### Внутренняя аутентификация
- Проверка токена в Redis
- Получение данных пользователя из локальной БД
- Проверка статуса аккаунта и разрешений

### Управление сессиями (sessions.py)

- Хранение сессий в Redis
- Поддержка:
  - Создание сессий
  - Верификация
  - Отзыв отдельных сессий
  - Отзыв всех сессий пользователя
- Автоматическое удаление истекших сессий

### JWT токены (jwtcodec.py)

- Кодирование/декодирование JWT токенов
- Проверка:
  - Срока действия
  - Подписи
  - Издателя
- Поддержка пользовательских claims

### OAuth интеграция (oauth.py)

Поддерживаемые провайдеры:
- Google
- Facebook
- GitHub

Функционал:
- Авторизация через OAuth провайдеров
- Получение профиля пользователя
- Создание/обновление локального профиля

### Валидация (validations.py)

Модели валидации для:
- Регистрации пользователей
- Входа в систему
- OAuth данных
- JWT payload
- Ответов API

### Email функционал (email.py)

- Отправка писем через Mailgun
- Поддержка шаблонов
- Мультиязычность (ru/en)
- Подтверждение email
- Сброс пароля

## API Endpoints (resolvers.py)

### Мутации
- `login` - вход в систему
- `getSession` - получение текущей сессии
- `confirmEmail` - подтверждение email
- `registerUser` - регистрация пользователя
- `sendLink` - отправка ссылки для входа

### Запросы
- `logout` - выход из системы
- `isEmailUsed` - проверка использования email

## Безопасность

### Хеширование паролей (identity.py)
- Использование bcrypt с SHA-256
- Настраиваемое количество раундов
- Защита от timing-атак

### Защита от брутфорса
- Блокировка аккаунта после 5 неудачных попыток
- Время блокировки: 30 минут
- Сброс счетчика после успешного входа

## Обработка заголовков авторизации

### Особенности работы с заголовками в Starlette

При работе с заголовками в Starlette/FastAPI необходимо учитывать следующие особенности:

1. **Регистр заголовков**: Заголовки в объекте `Request` чувствительны к регистру. Для надежного получения заголовка `Authorization` следует использовать регистронезависимый поиск.

2. **Формат Bearer токена**: Токен может приходить как с префиксом `Bearer `, так и без него. Необходимо обрабатывать оба варианта.

### Правильное получение заголовка авторизации

```python
# Получение заголовка с учетом регистра
headers_dict = dict(req.headers.items())
token = None

# Ищем заголовок независимо от регистра
for header_name, header_value in headers_dict.items():
    if header_name.lower() == SESSION_TOKEN_HEADER.lower():
        token = header_value
        break

# Обработка Bearer префикса
if token and token.startswith("Bearer "):
    token = token.split("Bearer ")[1].strip()
```

### Распространенные проблемы и их решения

1. **Проблема**: Заголовок не находится при прямом обращении `req.headers.get("Authorization")`
   **Решение**: Использовать регистронезависимый поиск по всем заголовкам

2. **Проблема**: Токен приходит с префиксом "Bearer" в одних запросах и без него в других
   **Решение**: Всегда проверять и обрабатывать оба варианта

3. **Проблема**: Токен декодируется, но сессия не находится в Redis
   **Решение**: Проверить формирование ключа сессии и добавить автоматическое создание сессии для валидных токенов

4. **Проблема**: Ошибки при декодировании JWT вызывают исключения
   **Решение**: Обернуть декодирование в try-except и возвращать None вместо вызова исключений

## Конфигурация

Основные настройки в settings.py:
- `SESSION_TOKEN_LIFE_SPAN` - время жизни сессии
- `ONETIME_TOKEN_LIFE_SPAN` - время жизни одноразовых токенов
- `JWT_SECRET_KEY` - секретный ключ для JWT
- `JWT_ALGORITHM` - алгоритм подписи JWT

## Примеры использования

### Аутентификация

```python
# Проверка авторизации
user_id, roles = await check_auth(request)

# Добавление роли
await add_user_role(user_id, ["author"])

# Создание сессии
token = await create_local_session(author)
```

### OAuth авторизация

```python
# Инициация OAuth процесса
await oauth_login(request)

# Обработка callback
response = await oauth_authorize(request)
```

### 1. Базовая авторизация на фронтенде

```typescript
// pages/Login.tsx
// Предполагается, что AuthClient и createAuth импортированы корректно
// import { AuthClient } from '../auth/AuthClient'; // Путь может отличаться
// import { createAuth } from '../auth/useAuth';   // Путь может отличаться
import { Component, Show } from 'solid-js'; // Show для условного рендеринга

export const LoginPage: Component = () => {
  // Клиент и хук авторизации (пример из client/auth/useAuth.ts)
  // const authClient = new AuthClient(/* baseUrl or other config */);
  // const auth = createAuth(authClient);
  // Для простоты примера, предположим, что auth уже доступен через контекст или пропсы
  // В реальном приложении используйте useAuthContext() если он настроен
  const { store, login } = useAuthContext(); // Пример, если используется контекст

  const handleSubmit = async (event: SubmitEvent) => {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const emailInput = form.elements.namedItem('email') as HTMLInputElement;
    const passwordInput = form.elements.namedItem('password') as HTMLInputElement;

    if (!emailInput || !passwordInput) {
      console.error("Email or password input not found");
      return;
    }

    const success = await login({
      email: emailInput.value,
      password: passwordInput.value
    });

    if (success) {
      console.log('Login successful, redirecting...');
      // window.location.href = '/'; // Раскомментируйте для реального редиректа
    } else {
      // Ошибка уже должна быть в store().error, обработанная в useAuth
      console.error('Login failed:', store().error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label for="email">Email:</label>
        <input id="email" name="email" type="email" required />
      </div>
      <div>
        <label for="password">Пароль:</label>
        <input id="password" name="password" type="password" required />
      </div>
      <button type="submit" disabled={store().isLoading}>
        {store().isLoading ? 'Вход...' : 'Войти'}
      </button>
      <Show when={store().error}>
        <p style={{ color: 'red' }}>{store().error}</p>
      </Show>
    </form>
  );
}
```

### 2. Защита компонента с помощью ролей

```typescript
// components/AdminPanel.tsx
import { useAuthContext } from '../auth'

export const AdminPanel: Component = () => {
  const auth = useAuthContext()
  
  // Проверяем наличие роли админа
  if (!auth.hasRole('admin')) {
    return <div>Доступ запрещен</div>
  }
  
  return (
    <div>
      <h1>Панель администратора</h1>
      {/* Контент админки */}
    </div>
  )
}
```

### 3. OAuth авторизация через Google

```typescript
// components/GoogleLoginButton.tsx
import { Component } from 'solid-js';

export const GoogleLoginButton: Component = () => {
  const handleGoogleLogin = () => {
    // Предполагается, что API_BASE_URL настроен глобально или импортирован
    // const API_BASE_URL = 'http://localhost:8000'; // Пример
    // window.location.href = `${API_BASE_URL}/auth/login/google`;
    // Или если пути относительные и сервер на том же домене:
    window.location.href = '/auth/login/google';
  };

  return (
    <button onClick={handleGoogleLogin}>
      Войти через Google
    </button>
  );
}
```

### 4. Работа с пользователем на бэкенде

```python
# routes/articles.py
# Предполагаемые импорты:
# from starlette.requests import Request
# from starlette.responses import JSONResponse
# from sqlalchemy.orm import Session
# from ..dependencies import get_db_session # Пример получения сессии БД
# from ..auth.decorators import login_required # Ваш декоратор
# from ..auth.orm import Author # Модель пользователя
# from ..models.article import Article # Модель статьи (пример)

# @login_required # Декоратор проверяет аутентификацию и добавляет user в request
async def create_article_example(request: Request): # Используем Request из Starlette
    """
    Пример создания статьи с проверкой прав.
    В реальном приложении используйте DI для сессии БД (например, FastAPI Depends).
    """
    user: Author = request.user # request.user добавляется декоратором @login_required

    # Проверяем право на создание статей (метод из модели auth.orm.Author)
    if not user.has_permission('articles', 'create'):
        return JSONResponse({'error': 'Недостаточно прав для создания статьи'}, status_code=403)

    try:
        article_data = await request.json()
        title = article_data.get('title')
        content = article_data.get('content')

        if not title or not content:
            return JSONResponse({'error': 'Title and content are required'}, status_code=400)

    except ValueError: # Если JSON некорректен
        return JSONResponse({'error': 'Invalid JSON data'}, status_code=400)

    # Пример работы с БД. В реальном приложении сессия db будет получена через DI.
    # Здесь db - это заглушка, замените на вашу реальную логику работы с БД.
    # Пример:
    # with get_db_session() as db: # Получение сессии SQLAlchemy
    #     new_article = Article(
    #         title=title,
    #         content=content,
    #         author_id=user.id # Связываем статью с автором
    #     )
    #     db.add(new_article)
    #     db.commit()
    #     db.refresh(new_article)
    #     return JSONResponse({'id': new_article.id, 'title': new_article.title}, status_code=201)

    # Заглушка для примера в документации
    mock_article_id = 123
    print(f"User {user.id} ({user.email}) is creating article '{title}'.")
    return JSONResponse({'id': mock_article_id, 'title': title}, status_code=201)
```

### 5. Проверка прав в GraphQL резолверах

```python
# resolvers/mutations.py
from auth.decorators import login_required
from auth.models import Author

@login_required
async def update_article(_, info, article_id: int, data: dict):
    """
    Обновление статьи с проверкой прав
    """
    user: Author = info.context.user
    
    # Получаем статью
    article = db.query(Article).get(article_id)
    if not article:
        raise GraphQLError('Статья не найдена')
        
    # Проверяем права на редактирование
    if not user.has_permission('articles', 'edit'):
        raise GraphQLError('Недостаточно прав')
        
    # Обновляем поля
    article.title = data.get('title', article.title)
    article.content = data.get('content', article.content)
    
    db.commit()
    return article
```

### 6. Создание пользователя с ролями

```python
# scripts/create_admin.py
from auth.models import Author, Role
from auth.password import hash_password

def create_admin(email: str, password: str):
    """Создание администратора"""
    
    # Получаем роль админа
    admin_role = db.query(Role).filter(Role.id == 'admin').first()
    
    # Создаем пользователя
    admin = Author(
        email=email,
        password=hash_password(password),
        is_active=True,
        email_verified=True
    )
    
    # Назначаем роль
    admin.roles.append(admin_role)
    
    # Сохраняем
    db.add(admin)
    db.commit()
    
    return admin
```

### 7. Работа с сессиями

```python
# auth/session_management.py (примерное название файла)
# Предполагаемые импорты:
# from starlette.responses import RedirectResponse
# from starlette.requests import Request
# from ..auth.orm import Author # Модель пользователя
# from ..auth.token import TokenStorage # Ваш модуль для работы с токенами
# from ..settings import SESSION_COOKIE_MAX_AGE, SESSION_COOKIE_NAME, SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE

# Замените FRONTEND_URL_AUTH_SUCCESS и FRONTEND_URL_LOGOUT на реальные URL из настроек
FRONTEND_URL_AUTH_SUCCESS = "/auth/success" # Пример
FRONTEND_URL_LOGOUT = "/logout" # Пример


async def login_user_session(request: Request, user: Author, response_class=RedirectResponse):
    """
    Создание сессии пользователя и установка cookie.
    """
    if not hasattr(user, 'id'): # Проверка наличия id у пользователя
        raise ValueError("User object must have an id attribute")

    # Создаем токен сессии (TokenStorage из вашего модуля auth.token)
    session_token = TokenStorage.create_session(str(user.id)) # ID пользователя обычно число, приводим к строке если нужно

    # Устанавливаем cookie
    # В реальном приложении FRONTEND_URL_AUTH_SUCCESS должен вести на страницу вашего фронтенда
    response = response_class(url=FRONTEND_URL_AUTH_SUCCESS)
    response.set_cookie(
        key=SESSION_COOKIE_NAME, # 'session_token' из settings.py
        value=session_token,
        httponly=SESSION_COOKIE_HTTPONLY, # True из settings.py
        secure=SESSION_COOKIE_SECURE,     # True для HTTPS из settings.py
        samesite=SESSION_COOKIE_SAMESITE, # 'lax' из settings.py
        max_age=SESSION_COOKIE_MAX_AGE    # 30 дней в секундах из settings.py
    )
    print(f"Session created for user {user.id}. Token: {session_token[:10]}...") # Логируем для отладки
    return response

async def logout_user_session(request: Request, response_class=RedirectResponse):
    """
    Завершение сессии пользователя и удаление cookie.
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    if session_token:
        # Удаляем токен из хранилища (TokenStorage из вашего модуля auth.token)
        TokenStorage.delete_session(session_token)
        print(f"Session token {session_token[:10]}... deleted from storage.")

    # Удаляем cookie
    # В реальном приложении FRONTEND_URL_LOGOUT должен вести на страницу вашего фронтенда
    response = response_class(url=FRONTEND_URL_LOGOUT)
    response.delete_cookie(SESSION_COOKIE_NAME)
    print(f"Cookie {SESSION_COOKIE_NAME} deleted.")
    return response
```

### 8. Проверка CSRF в формах

```typescript
// components/ProfileForm.tsx
// import { useAuthContext } from '../auth'; // Предполагаем, что auth есть в контексте
import { Component, createSignal, Show } from 'solid-js';

export const ProfileForm: Component = () => {
  const { store, checkAuth } = useAuthContext(); // Пример получения из контекста
  const [message, setMessage] = createSignal<string | null>(null);
  const [error, setError] = createSignal<string | null>(null);

  const handleSubmit = async (event: SubmitEvent) => {
    event.preventDefault();
    setMessage(null);
    setError(null);
    const form = event.currentTarget as HTMLFormElement;
    const formData = new FormData(form);

    // ВАЖНО: Получение CSRF-токена из cookie - это один из способов.
    // Если CSRF-токен устанавливается как httpOnly cookie, то он будет автоматически
    // отправляться браузером, и его не нужно доставать вручную для fetch,
    // если сервер настроен на его проверку из заголовка (например, X-CSRF-Token),
    // который fetch *не* устанавливает автоматически для httpOnly cookie.
    // Либо сервер может предоставлять CSRF-токен через специальный эндпоинт.
    // Представленный ниже способ подходит, если CSRF-токен доступен для JS.
    const csrfToken = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrf_token=')) // Имя cookie может отличаться
      ?.split('=')[1];

    if (!csrfToken) {
      // setError('CSRF token not found. Please refresh the page.');
      // В продакшене CSRF-токен должен быть всегда. Этот лог для отладки.
      console.warn('CSRF token not found in cookies. Ensure it is set by the server.');
      // Для данного примера, если токен не найден, можно либо прервать, либо положиться на серверную проверку.
      // Для большей безопасности, прерываем, если CSRF-защита критична на клиенте.
    }

    try {
      // Замените '/api/profile' на ваш реальный эндпоинт
      const response = await fetch('/api/profile', {
        method: 'POST',
        headers: {
          // Сервер должен быть настроен на чтение этого заголовка
          // если CSRF токен не отправляется автоматически с httpOnly cookie.
          ...(csrfToken && { 'X-CSRF-Token': csrfToken }),
          // 'Content-Type': 'application/json' // Если отправляете JSON
        },
        body: formData // FormData отправится как 'multipart/form-data'
                       // Если нужно JSON: body: JSON.stringify(Object.fromEntries(formData))
      });

      if (response.ok) {
        const result = await response.json();
        setMessage(result.message || 'Профиль успешно обновлен!');
        checkAuth(); // Обновить данные пользователя в сторе
      } else {
        const errData = await response.json();
        setError(errData.error || `Ошибка: ${response.status}`);
      }
    } catch (err) {
      console.error('Profile update error:', err);
      setError('Не удалось обновить профиль. Попробуйте позже.');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label for="name">Имя:</label>
        <input id="name" name="name" defaultValue={store().user?.name || ''} />
      </div>
      {/* Другие поля профиля */}
      <button type="submit">Сохранить изменения</button>
      <Show when={message()}>
        <p style={{ color: 'green' }}>{message()}</p>
      </Show>
      <Show when={error()}>
        <p style={{ color: 'red' }}>{error()}</p>
      </Show>
    </form>
  );
}
```

### 9. Кастомные валидаторы для форм

```typescript
// validators/auth.ts
export const validatePassword = (password: string): string[] => {
  const errors: string[] = []
  
  if (password.length < 8) {
    errors.push('Пароль должен быть не менее 8 символов')
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('Пароль должен содержать заглавную букву')
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('Пароль должен содержать цифру')
  }
  
  return errors
}

// components/RegisterForm.tsx
import { validatePassword } from '../validators/auth'

export const RegisterForm: Component = () => {
  const [errors, setErrors] = createSignal<string[]>([])
  
  const handleSubmit = async (e: Event) => {
    e.preventDefault()
    const form = e.target as HTMLFormElement
    const data = new FormData(form)
    
    // Валидация пароля
    const password = data.get('password') as string
    const passwordErrors = validatePassword(password)
    
    if (passwordErrors.length > 0) {
      setErrors(passwordErrors)
      return
    }
    
    // Отправка формы...
  }
  
  return (
    <form onSubmit={handleSubmit}>
      <input name="password" type="password" />
      {errors().map(error => (
        <div class="error">{error}</div>
      ))}
      <button type="submit">Регистрация</button>
    </form>
  )
}
```

### 10. Интеграция с внешними сервисами

```python
# services/notifications.py
from auth.models import Author

async def notify_login(user: Author, ip: str, device: str):
    """Отправка уведомления о новом входе"""
    
    # Формируем текст
    text = f"""
    Новый вход в аккаунт:
    IP: {ip}
    Устройство: {device}
    Время: {datetime.now()}
    """
    
    # Отправляем email
    await send_email(
        to=user.email,
        subject='Новый вход в аккаунт',
        text=text
    )
    
    # Логируем
    logger.info(f'New login for user {user.id} from {ip}')
```

## Тестирование

### 1. Тест OAuth авторизации

```python
# tests/test_oauth.py
@pytest.mark.asyncio
async def test_google_oauth_success(client, mock_google):
    # Мокаем ответ от Google
    mock_google.return_value = {
        'id': '123',
        'email': 'test@gmail.com',
        'name': 'Test User'
    }
    
    # Запрос на авторизацию
    response = await client.get('/auth/login/google')
    assert response.status_code == 302
    
    # Проверяем редирект
    assert 'accounts.google.com' in response.headers['location']
    
    # Проверяем сессию
    assert 'state' in client.session
    assert 'code_verifier' in client.session
```

### 2. Тест ролей и разрешений

```python
# tests/test_permissions.py
def test_user_permissions():
    # Создаем тестовые данные
    role = Role(id='editor', name='Editor')
    permission = Permission(
        id='articles:edit',
        resource='articles',
        operation='edit'
    )
    role.permissions.append(permission)
    
    user = Author(email='test@test.com')
    user.roles.append(role)
    
    # Проверяем разрешения
    assert user.has_permission('articles', 'edit')
    assert not user.has_permission('articles', 'delete')
```

## Безопасность

### 1. Rate Limiting

```python
# middleware/rate_limit.py
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from redis import Redis

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Получаем IP
        ip = request.client.host
        
        # Проверяем лимиты в Redis
        redis = Redis()
        key = f'rate_limit:{ip}'
        
        # Увеличиваем счетчик
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 60)  # TTL 60 секунд
            
        # Проверяем лимит
        if count > 100:  # 100 запросов в минуту
            return JSONResponse(
                {'error': 'Too many requests'},
                status_code=429
            )
            
        return await call_next(request)
```

### 2. Защита от брутфорса

```python
# auth/login.py
async def handle_login_attempt(user: Author, success: bool):
    """Обработка попытки входа"""
    
    if not success:
        # Увеличиваем счетчик неудачных попыток
        user.increment_failed_login()
        
        if user.is_locked():
            # Аккаунт заблокирован
            raise AuthError(
                'Account is locked. Try again later.',
                'ACCOUNT_LOCKED'
            )
    else:
        # Сбрасываем счетчик при успешном входе
        user.reset_failed_login()
```

## Мониторинг

### 1. Логирование событий авторизации

```python
# auth/logging.py
import structlog

logger = structlog.get_logger()

def log_auth_event(
    event_type: str,
    user_id: int = None,
    success: bool = True,
    **kwargs
):
    """
    Логирование событий авторизации
    
    Args:
        event_type: Тип события (login, logout, etc)
        user_id: ID пользователя
        success: Успешность операции
        **kwargs: Дополнительные поля
    """
    logger.info(
        'auth_event',
        event_type=event_type,
        user_id=user_id,
        success=success,
        **kwargs
    )
```

### 2. Метрики для Prometheus

```python
# metrics/auth.py
from prometheus_client import Counter, Histogram

# Счетчики
login_attempts = Counter(
    'auth_login_attempts_total',
    'Number of login attempts',
    ['success']
)

oauth_logins = Counter(
    'auth_oauth_logins_total',
    'Number of OAuth logins',
    ['provider']
)

# Гистограммы
login_duration = Histogram(
    'auth_login_duration_seconds',
    'Time spent processing login'
)
``` 