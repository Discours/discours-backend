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
    console.debug(`[Frontend] Authorization header: Bearer ${token.substring(0, 20)}...`)
  } else {
    console.warn('[Frontend] Токен не найден или слишком короткий')
    console.debug(`[Frontend] Local token: ${localToken ? 'present' : 'missing'}`)
    console.debug(`[Frontend] Cookie token: ${cookieToken ? 'present' : 'missing'}`)
  }

  // Добавляем CSRF-токен, если он есть
  const csrfToken = getCsrfTokenFromCookie()
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
    console.debug('Добавлен CSRF-токен в запрос')
  }

  console.debug(`[Frontend] Все заголовки: ${Object.keys(headers).join(', ')}`)
  return headers
}

/**
 * Выполняет GraphQL запрос с retry логикой для 503 ошибок
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
  const maxRetries = 3
  const retryDelay = 500 // 500ms базовая задержка

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`[GraphQL] Making request to ${endpoint} (attempt ${attempt}/${maxRetries})`)
      console.log(`[GraphQL] Query: ${query.substring(0, 100)}...`)

      // Используем существующую функцию для получения всех необходимых заголовков
      const headers = getRequestHeaders()
      console.log(
        `[GraphQL] Заголовки установлены, Authorization: ${headers['Authorization'] ? 'присутствует' : 'отсутствует'}`
      )

      // Дополнительное логирование заголовков
      console.log(`[GraphQL] Все заголовки: ${Object.keys(headers).join(', ')}`)
      if (headers['Authorization']) {
        console.log(`[GraphQL] Authorization header: ${headers['Authorization'].substring(0, 30)}...`)
      }

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

      // Если получили 503 и это не последняя попытка, повторяем запрос
      if (response.status === 503 && attempt < maxRetries) {
        const delay = retryDelay * attempt // Экспоненциальная задержка
        console.log(`[GraphQL] Got 503 error, retrying after ${delay}ms...`)
        await new Promise((resolve) => setTimeout(resolve, delay))
        continue
      }

      if (!response.ok) {
        if (response.status === 401) {
          console.log('[GraphQL] UnauthorizedError response, clearing auth tokens')
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
        const hasUnauthorizedError = result.errors.some(
          (error: { message?: string }) =>
            error.message?.toLowerCase().includes('unauthorized') ||
            error.message?.toLowerCase().includes('please login')
        )

        if (hasUnauthorizedError) {
          console.log('[GraphQL] UnauthorizedError error in response, clearing auth tokens')
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
      // Если это последняя попытка или ошибка не 503, пробрасываем ошибку
      if (attempt === maxRetries || !(error instanceof Error) || !error.message.includes('503')) {
        console.error('[GraphQL] Query error:', error)
        throw error
      }

      // Для других ошибок на промежуточных попытках просто логируем
      console.warn(`[GraphQL] Attempt ${attempt} failed, retrying...`, error.message)
    }
  }

  // Этот код никогда не должен выполниться, но добавляем для TypeScript
  throw new Error('Max retries exceeded')
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
