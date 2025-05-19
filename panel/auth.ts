/**
 * Модуль авторизации
 * @module auth
 */

// Экспортируем константы для использования в других модулях
export const AUTH_TOKEN_KEY = 'auth_token'
export const CSRF_TOKEN_KEY = 'csrf_token'

/**
 * Интерфейс для учетных данных
 */
export interface Credentials {
  email: string
  password: string
}

/**
 * Интерфейс для результата авторизации
 */
export interface LoginResult {
  success: boolean
  token?: string
  error?: string
}

/**
 * Интерфейс для ответа API при логине
 */
interface LoginResponse {
  login: LoginResult
}

/**
 * Получает токен авторизации из cookie
 * @returns Токен или пустую строку, если токен не найден
 */
export function getAuthTokenFromCookie(): string {
  const cookieItems = document.cookie.split(';')
  for (const item of cookieItems) {
    const [name, value] = item.trim().split('=')
    if (name === AUTH_TOKEN_KEY) {
      return value
    }
  }
  return ''
}

/**
 * Получает CSRF-токен из cookie
 * @returns CSRF-токен или пустую строку, если токен не найден
 */
export function getCsrfTokenFromCookie(): string {
  const cookieItems = document.cookie.split(';')
  for (const item of cookieItems) {
    const [name, value] = item.trim().split('=')
    if (name === CSRF_TOKEN_KEY) {
      return value
    }
  }
  return ''
}

/**
 * Проверяет, авторизован ли пользователь
 * @returns Статус авторизации
 */
export function isAuthenticated(): boolean {
  // Проверяем наличие cookie auth_token
  const cookieToken = getAuthTokenFromCookie()
  const hasCookie = !!cookieToken && cookieToken.length > 10

  // Проверяем наличие токена в localStorage
  const localToken = localStorage.getItem(AUTH_TOKEN_KEY)
  const hasLocalToken = !!localToken && localToken.length > 10

  // Пользователь авторизован, если есть cookie или токен в localStorage
  return hasCookie || hasLocalToken
}

/**
 * Выполняет выход из системы
 * @param callback - Функция обратного вызова после выхода
 */
export function logout(callback?: () => void): void {
  // Очищаем токен из localStorage
  localStorage.removeItem(AUTH_TOKEN_KEY)

  // Для удаления cookie устанавливаем ей истекшее время жизни
  document.cookie = `${AUTH_TOKEN_KEY}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`

  // Дополнительно пытаемся сделать запрос на сервер для удаления серверных сессий
  try {
    fetch('/auth/logout', {
      method: 'POST',  // Используем POST вместо GET для операций изменения состояния
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfTokenFromCookie()  // Добавляем CSRF токен если он есть
      }
    }).catch((e) => {
      console.error('Ошибка при запросе на выход:', e)
    })
  } catch (e) {
    console.error('Ошибка при выходе:', e)
  }

  // Вызываем функцию обратного вызова после очистки токенов
  if (callback) callback()
}

/**
 * Выполняет вход в систему используя GraphQL-запрос
 * @param credentials - Учетные данные
 * @returns Результат авторизации
 */
export async function login(credentials: Credentials): Promise<boolean> {
  try {
    console.log('Отправка запроса авторизации через GraphQL')
    
    const response = await fetch(`${location.origin}/graphql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRF-Token': getCsrfTokenFromCookie()  // Добавляем CSRF токен если он есть
      },
      credentials: 'include',  // Важно для обработки cookies
      body: JSON.stringify({
        query: `
          mutation Login($email: String!, $password: String!) {
            login(email: $email, password: $password) {
              success
              token
              error
            }
          }
        `,
        variables: {
          email: credentials.email,
          password: credentials.password
        }
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Ошибка HTTP:', response.status, errorText)
      throw new Error(`HTTP error: ${response.status} ${response.statusText}`)
    }

    const result = await response.json()
    console.log('Результат авторизации:', result)

    if (result?.data?.login?.success) {
      // Проверяем, установил ли сервер cookie
      const cookieToken = getAuthTokenFromCookie()
      const hasCookie = !!cookieToken && cookieToken.length > 10

      // Если cookie не установлена, но есть токен в ответе, сохраняем его в localStorage
      if (!hasCookie && result.data.login.token) {
        localStorage.setItem(AUTH_TOKEN_KEY, result.data.login.token)
      }

      return true
    }

    if (result.errors && result.errors.length > 0) {
      throw new Error(result.errors[0].message || 'Ошибка авторизации')
    }

    throw new Error(result?.data?.login?.error || 'Неизвестная ошибка авторизации')
  } catch (error) {
    console.error('Ошибка при входе:', error)
    throw error
  }
}
