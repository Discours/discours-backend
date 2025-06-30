/**
 * API-клиент для работы с GraphQL
 * @module api
 */

import {
  AUTH_TOKEN_KEY,
  clearAuthTokens,
  getAuthTokenFromCookie,
  getCsrfTokenFromCookie
} from '../utils/auth'

/**
 * Тип для произвольных данных GraphQL
 */
type GraphQLData = Record<string, unknown>

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
    headers['X-CSRF-Token'] = csrfToken
    console.debug('Добавлен CSRF-токен в запрос')
  }

  return headers
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

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: getRequestHeaders(),
      credentials: 'include',
      body: JSON.stringify({
        query,
        variables
      })
    })

    console.log(`[GraphQL] Response status: ${response.status}`)

    if (!response.ok) {
      if (response.status === 401) {
        console.log('[GraphQL] Unauthorized response, clearing auth tokens')
        clearAuthTokens()
        // Перенаправляем на страницу входа только если мы не на ней
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login'
        }
      }
      const errorText = await response.text()
      throw new Error(`HTTP error: ${response.status} ${errorText}`)
    }

    const result = await response.json()
    console.log('[GraphQL] Response received:', result)

    if (result.errors) {
      // Проверяем ошибки авторизации
      const hasUnauthorized = result.errors.some(
        (error: { message?: string }) =>
          error.message?.toLowerCase().includes('unauthorized') ||
          error.message?.toLowerCase().includes('please login')
      )

      if (hasUnauthorized) {
        console.log('[GraphQL] Unauthorized error in response, clearing auth tokens')
        clearAuthTokens()
        // Перенаправляем на страницу входа только если мы не на ней
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login'
        }
      }

      // Handle GraphQL errors
      const errorMessage = result.errors.map((e: { message?: string }) => e.message).join(', ')
      throw new Error(`GraphQL error: ${errorMessage}`)
    }

    return result.data
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
