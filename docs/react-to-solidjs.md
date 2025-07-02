# Миграция с React 18 на SolidStart: Comprehensive Guide

## 1. Введение

### 1.1 Что такое SolidStart?

SolidStart - это метафреймворк для SolidJS, который предоставляет полнофункциональное решение для создания веб-приложений. Ключевые особенности:

- Полностью изоморфное приложение (работает на клиенте и сервере)
- Встроенная поддержка SSR, SSG и CSR
- Интеграция с Vite и Nitro
- Гибкая маршрутизация
- Встроенные серверные функции и действия

### 1.2 Основные различия между React и SolidStart

| Характеристика | React 18 | SolidStart |
|---------------|----------|------------|
| Рендеринг | Virtual DOM | Компиляция и прямое обновление DOM |
| Серверный рендеринг | Сложная настройка | Встроенная поддержка |
| Размер бандла | ~40 кБ | ~7.7 кБ |
| Реактивность | Хуки с зависимостями | Сигналы без явных зависимостей |
| Маршрутизация | react-router | @solidjs/router |

## 2. Подготовка проекта

### 2.1 Установка зависимостей

```bash
# Удаление React зависимостей
npm uninstall react react-dom react-router-dom

# Установка SolidStart и связанных библиотек
npm install @solidjs/start solid-js @solidjs/router
```

### 2.2 Обновление конфигурации

#### Vite Configuration (`vite.config.ts`)
```typescript
import { defineConfig } from 'vite';
import solid from 'solid-start/vite';

export default defineConfig({
  plugins: [solid()],
  // Дополнительные настройки
});
```

#### TypeScript Configuration (`tsconfig.json`)
```json
{
  "compilerOptions": {
    "jsx": "preserve",
    "jsxImportSource": "solid-js",
    "types": ["solid-start/env"]
  }
}
```

#### SolidStart Configuration (`app.config.ts`)
```typescript
import { defineConfig } from "@solidjs/start/config";

export default defineConfig({
  server: {
    // Настройки сервера, например:
    preset: "netlify" // или другой провайдер
  },
  // Дополнительные настройки
});
```

## 3. Миграция компонентов и логики

### 3.1 Состояние и реактивность

#### React:
```typescript
const [count, setCount] = useState(0);
```

#### SolidJS:
```typescript
const [count, setCount] = createSignal(0);
// Использование: count(), setCount(newValue)
```

### 3.2 Серверные функции и загрузка данных

В SolidStart есть несколько способов работы с данными:

#### Серверная функция
```typescript
// server/api.ts
export function getUser(id: string) {
  return db.users.findUnique({ where: { id } });
}

// Component
export default function UserProfile() {
  const user = createAsync(() => getUser(params.id));

  return <div>{user()?.name}</div>;
}
```

#### Действия (Actions)
```typescript
export function updateProfile(formData: FormData) {
  'use server';
  const name = formData.get('name');
  // Логика обновления профиля
}
```

### 3.3 Маршрутизация

```typescript
// src/routes/index.tsx
import { A } from "@solidjs/router";

export default function HomePage() {
  return (
    <div>
      <A href="/about">О нас</A>
      <A href="/profile">Профиль</A>
    </div>
  );
}

// src/routes/profile.tsx
export default function ProfilePage() {
  return <div>Профиль пользователя</div>;
}
```

## 4. Оптимизация и производительность

### 4.1 Мемоизация

```typescript
// Кэширование сложных вычислений
const sortedUsers = createMemo(() =>
  users().sort((a, b) => a.name.localeCompare(b.name))
);

// Ленивая загрузка
const UserList = lazy(() => import('./UserList'));
```

### 4.2 Серверный рендеринг и предзагрузка

```typescript
// Предзагрузка данных
export function routeData() {
  return {
    user: createAsync(() => fetchUser())
  };
}

export default function UserPage() {
  const user = useRouteData<typeof routeData>();
  return <div>{user().name}</div>;
}
```

## 5. Особенности миграции

### 5.1 Ключевые изменения
- Замена `useState` на `createSignal`
- Использование `createAsync` вместо `useEffect` для загрузки данных
- Серверные функции с `'use server'`
- Маршрутизация через `@solidjs/router`

### 5.2 Потенциальные проблемы
- Переписать все React-специфичные хуки
- Адаптировать библиотеки компонентов
- Обновить тесты и CI/CD

## 6. Деплой

SolidStart поддерживает множество платформ:
- Netlify
- Vercel
- Cloudflare
- AWS
- Deno
- и другие

```typescript
// app.config.ts
export default defineConfig({
  server: {
    preset: "netlify" // Выберите вашу платформу
  }
});
```

## 7. Инструменты и экосистема

### Рекомендованные библиотеки
- Роутинг: `@solidjs/router`
- Состояние: Встроенные примитивы SolidJS
- Запросы: `@tanstack/solid-query`
- Девтулзы: `solid-devtools`

## 8. Миграция конкретных компонентов

### 8.1 Страница регистрации (RegisterPage)

#### React-версия
```typescript
import React from 'react'
import { Navigate } from 'react-router-dom'
import { RegisterForm } from '../components/auth/RegisterForm'
import { useAuthStore } from '../store/authStore'

export const RegisterPage: React.FC = () => {
  const { isAuthenticated } = useAuthStore()

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="min-h-screen ...">
      <RegisterForm />
    </div>
  )
}
```

#### SolidJS-версия
```typescript
import { Navigate } from '@solidjs/router'
import { Show } from 'solid-js'
import { RegisterForm } from '../components/auth/RegisterForm'
import { useAuthStore } from '../store/authStore'

export default function RegisterPage() {
  const { isAuthenticated } = useAuthStore()

  return (
    <Show when={!isAuthenticated()} fallback={<Navigate href="/" />}>
      <div class="min-h-screen ...">
        <RegisterForm />
      </div>
    </Show>
  )
}
```

#### Ключевые изменения
- Удаление импорта React
- Использование `@solidjs/router` вместо `react-router-dom`
- Замена `className` на `class`
- Использование `Show` для условного рендеринга
- Вызов `isAuthenticated()` как функции
- Использование `href` вместо `to`
- Экспорт по умолчанию вместо именованного экспорта

### Рекомендации
- Всегда используйте `Show` для условного рендеринга
- Помните, что сигналы в SolidJS - это функции
- Следите за совместимостью импортов и маршрутизации

## 9. UI Component Migration

### 9.1 Key Differences in Component Structure

When migrating UI components from React to SolidJS, several key changes are necessary:

1. **Props Handling**
   - Replace `React.FC<Props>` with function component syntax
   - Use object destructuring for props instead of individual parameters
   - Replace `className` with `class`
   - Use `props.children` instead of `children` prop

2. **Type Annotations**
   - Use TypeScript interfaces for props
   - Explicitly type `children` as `any` or a more specific type
   - Remove React-specific type imports

3. **Event Handling**
   - Use SolidJS event types (e.g., `InputEvent`)
   - Modify event handler signatures to match SolidJS conventions

### 9.2 Component Migration Example

#### React Component
```typescript
import React from 'react'
import { clsx } from 'clsx'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary'
  fullWidth?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  fullWidth = false,
  className,
  children,
  ...props
}) => {
  const classes = clsx(
    'button',
    variant === 'primary' && 'bg-blue-500',
    fullWidth && 'w-full',
    className
  )

  return (
    <button className={classes} {...props}>
      {children}
    </button>
  )
}
```

#### SolidJS Component
```typescript
import { clsx } from 'clsx'

interface ButtonProps {
  variant?: 'primary' | 'secondary'
  fullWidth?: boolean
  class?: string
  children: any
  disabled?: boolean
  type?: 'button' | 'submit'
  onClick?: () => void
}

export const Button = (props: ButtonProps) => {
  const classes = clsx(
    'button',
    props.variant === 'primary' && 'bg-blue-500',
    props.fullWidth && 'w-full',
    props.class
  )

  return (
    <button
      class={classes}
      disabled={props.disabled}
      type={props.type || 'button'}
      onClick={props.onClick}
    >
      {props.children}
    </button>
  )
}
```

### 9.3 Key Migration Strategies

- Replace `React.FC` with standard function components
- Use `props` object instead of individual parameters
- Replace `className` with `class`
- Modify event handling to match SolidJS patterns
- Remove React-specific lifecycle methods
- Use SolidJS primitives like `createEffect` for side effects

## Заключение

Миграция на SolidStart требует внимательного подхода, но предоставляет значительные преимущества в производительности, простоте разработки и серверных возможностях.

### Рекомендации
- Мигрируйте постепенно
- Пишите тесты на каждом этапе
- Используйте инструменты совместимости

---

Этот гайд поможет вам систематически и безопасно мигрировать ваш проект на SolidStart, сохраняя существующую функциональность и улучшая производительность.
