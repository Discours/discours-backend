/**
 * Модуль авторизации
 * @module auth
 */

import { query } from './graphql'

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
 * Константа для имени ключа токена в localStorage
 */
const AUTH_TOKEN_KEY = 'auth_token'

/**
 * Константа для имени ключа токена в cookie
 */
const AUTH_COOKIE_NAME = 'auth_token'

/**
 * Получает токен авторизации из cookie
 * @returns Токен или пустую строку, если токен не найден
 */
function getAuthTokenFromCookie(): string {
  const cookieItems = document.cookie.split(';')
  for (const item of cookieItems) {
    const [name, value] = item.trim().split('=')
    if (name === AUTH_COOKIE_NAME) {
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
  document.cookie = `${AUTH_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`

  // Дополнительно пытаемся сделать запрос на сервер для удаления серверных сессий
  try {
    fetch('/logout', { 
      method: 'GET',
      credentials: 'include'
    }).catch(e => {
      console.error('Ошибка при запросе на выход:', e)
    })
  } catch (e) {
    console.error('Ошибка при выходе:', e)
  }

  // Вызываем функцию обратного вызова после очистки токенов
  if (callback) callback()
}

/**
 * Выполняет вход в систему
 * @param credentials - Учетные данные
 * @returns Результат авторизации
 */
export async function login(credentials: Credentials): Promise<boolean> {
  try {
    // Используем query из graphql.ts для выполнения запроса
    const data = await query<LoginResponse>(
      `
      mutation Login($email: String!, $password: String!) {
        login(email: $email, password: $password) {
          success
          token
          error
        }
      }
    `,
      {
        email: credentials.email,
        password: credentials.password
      }
    )

    if (data?.login?.success) {
      // Проверяем, установил ли сервер cookie
      const cookieToken = getAuthTokenFromCookie()
      const hasCookie = !!cookieToken && cookieToken.length > 10

      // Если cookie не установлена, но есть токен в ответе, сохраняем его в localStorage
      if (!hasCookie && data.login.token) {
        localStorage.setItem(AUTH_TOKEN_KEY, data.login.token)
      }

      return true
    }

    throw new Error(data?.login?.error || 'Ошибка авторизации')
  } catch (error) {
    console.error('Ошибка при входе:', error)
    throw error
  }
}
