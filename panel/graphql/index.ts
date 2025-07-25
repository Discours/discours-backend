/**
 * API-клиент для работы с GraphQL
 * @module api
 */

import { AUTH_TOKEN_KEY, clearAuthTokens, getAuthTokenFromCookie } from '../utils/auth'

/**
 * Тип для произвольных данных GraphQL
 */
type GraphQLData = Record<string, unknown>

const CSRF_TOKEN_KEY = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'

function getCsrfTokenFromCookie(): string {
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
 * Возвращает заголовки для GraphQL запроса с учетом авторизации и CSRF
 * @returns Объект с заголовками
 */
function getRequestHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json'
  }

  // Проверяем наличие токена в localStorage
  const localToken = localStorage.getItem(AUTH_TOKEN_KEY)

  // Проверяем наличие токена в cookie
  const cookieToken = getAuthTokenFromCookie()

  // Используем токен из localStorage или cookie
  const token = localToken || cookieToken

  // Если есть токен, добавляем его в заголовок Authorization с префиксом Bearer
  if (token && token.length > 10) {
    headers['Authorization'] = `Bearer ${token}`
    console.debug('Отправка запроса с токеном авторизации')
  }

  // Добавляем CSRF-токен, если он есть
  const csrfToken = getCsrfTokenFromCookie()
  if (csrfToken) {
    headers[CSRF_HEADER_NAME] = csrfToken
    console.debug('Добавлен CSRF-токен в запрос')
  }

  return headers
}

interface GraphQLError extends Error {
  extensions?: {
    code?: string
  }
}

/**
 * Выполняет GraphQL запрос
 * @param endpoint - URL эндпоинта GraphQL
 * @param query - GraphQL запрос
 * @param variables - Переменные запроса
 * @returns Результат запроса
 */
export async function query<T = unknown>(
  endpoint: string,
  query: string,
  variables?: Record<string, unknown>
): Promise<T> {
  try {
    console.log(`[GraphQL] Making request to ${endpoint}`)
    console.log(`[GraphQL] Query: ${query.substring(0, 100)}...`)

    // Используем существующую функцию для получения всех необходимых заголовков
    const headers = getRequestHeaders()
    console.log(
      `[GraphQL] Заголовки установлены, Authorization: ${headers['Authorization'] ? 'присутствует' : 'отсутствует'}`
    )

    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({
        query,
        variables
      })
    })

    console.log(`[GraphQL] Response status: ${response.status}`)

    // Обработка HTTP-ошибок авторизации
    if (response.status === 401) {
      console.log('[GraphQL] Unauthorized response, clearing auth tokens')
      clearAuthTokens()
      // Перенаправляем на страницу входа только если мы не на ней
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
      throw new Error('Unauthorized')
    }

    const result = await response.json()
    console.log('[GraphQL] Response received:', result)

    // Обработка CSRF-ошибок
    if (result.errors) {
      const csrfError = result.errors.find((error: GraphQLError) =>
        ['CSRF_TOKEN_MISSING', 'CSRF_TOKEN_INVALID'].includes(error.extensions?.code ?? '')
      )

      if (csrfError) {
        console.error('[GraphQL] CSRF Error:', csrfError)

        // Принудительное обновление страницы для получения нового токена
        window.location.reload()

        throw new Error(`CSRF Error: ${csrfError.message}`)
      }

      // Обработка других GraphQL-ошибок
      const unauthorizedError = result.errors.find(
        (error: GraphQLError) =>
          error.message.toLowerCase().includes('unauthorized') ||
          error.message.toLowerCase().includes('please login')
      )

      if (unauthorizedError) {
        console.log('[GraphQL] Unauthorized response, clearing auth tokens')
        clearAuthTokens()

        // Перенаправляем на страницу входа только если мы не на ней
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login'
        }
        throw new Error('Unauthorized')
      }

      throw new Error(result.errors.map((e: GraphQLError) => e.message).join('; '))
    }

    return result.data as T
  } catch (error) {
    console.error('[GraphQL] Query error:', error)
    throw error
  }
}

/**
 * Выполняет GraphQL мутацию
 * @param url - URL для запроса
 * @param mutation - GraphQL мутация
 * @param variables - Переменные мутации
 * @returns Результат мутации
 */
export function mutate<T = GraphQLData>(
  url: string,
  mutation: string,
  variables: Record<string, unknown> = {}
): Promise<T> {
  return query<T>(url, mutation, variables)
}
