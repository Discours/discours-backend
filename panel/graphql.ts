/**
 * API-клиент для работы с GraphQL
 * @module api
 */

import { AUTH_TOKEN_KEY, CSRF_TOKEN_KEY, getAuthTokenFromCookie, getCsrfTokenFromCookie } from './auth'

/**
 * Тип для произвольных данных GraphQL
 */
type GraphQLData = Record<string, unknown>

/**
 * Обрабатывает ошибки от API
 * @param response - Ответ от сервера
 * @returns Обработанный текст ошибки
 */
async function handleApiError(response: Response): Promise<string> {
  try {
    const contentType = response.headers.get('content-type')

    if (contentType?.includes('application/json')) {
      const errorData = await response.json()

      // Проверяем GraphQL ошибки
      if (errorData.errors && errorData.errors.length > 0) {
        return errorData.errors[0].message
      }

      // Проверяем сообщение об ошибке
      if (errorData.error || errorData.message) {
        return errorData.error || errorData.message
      }
    }

    // Если не JSON или нет структурированной ошибки, читаем как текст
    const errorText = await response.text()
    return `Ошибка сервера: ${response.status} ${response.statusText}. ${errorText.substring(0, 100)}...`
  } catch (_e) {
    // Если не можем прочитать ответ
    return `Ошибка сервера: ${response.status} ${response.statusText}`
  }
}

/**
 * Проверяет наличие ошибок авторизации в ответе GraphQL
 * @param errors - Массив ошибок GraphQL
 * @returns true если есть ошибки авторизации
 */
function hasAuthErrors(errors: Array<{ message?: string; extensions?: { code?: string } }>): boolean {
  return errors.some(
    (error) =>
      (error.message &&
        (error.message.toLowerCase().includes('unauthorized') ||
          error.message.toLowerCase().includes('авторизации') ||
          error.message.toLowerCase().includes('authentication') ||
          error.message.toLowerCase().includes('unauthenticated') ||
          error.message.toLowerCase().includes('token'))) ||
      error.extensions?.code === 'UNAUTHENTICATED' ||
      error.extensions?.code === 'FORBIDDEN'
  )
}

/**
 * Подготавливает URL для GraphQL запроса
 * @param url - URL или путь для запроса
 * @returns Полный URL для запроса
 */
function prepareUrl(url: string): string {
  // В режиме локальной разработки всегда используем /graphql
  if (location.hostname === 'localhost') {
    return `${location.origin}/graphql`
  }

  // Если это относительный путь, добавляем к нему origin
  if (url.startsWith('/')) {
    return `${location.origin}${url}`
  }
  // Если это уже полный URL, используем как есть
  return url
}

/**
 * Возвращает заголовки для GraphQL запроса с учетом авторизации и CSRF
 * @returns Объект с заголовками
 */
function getRequestHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
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
 * @param url - URL для запроса
 * @param query - GraphQL запрос
 * @param variables - Переменные запроса
 * @returns Результат запроса
 */
export async function query<T = GraphQLData>(
  url: string,
  query: string,
  variables: Record<string, unknown> = {}
): Promise<T> {
  try {
    // Получаем все необходимые заголовки для запроса
    const headers = getRequestHeaders()

    // Подготавливаем полный URL
    const fullUrl = prepareUrl(url)
    console.debug('Отправка GraphQL запроса на:', fullUrl)

    const response = await fetch(fullUrl, {
      method: 'POST',
      headers,
      // Важно: credentials: 'include' - для передачи cookies с запросом
      credentials: 'include',
      body: JSON.stringify({
        query,
        variables
      })
    })

    // Проверяем статус ответа
    if (!response.ok) {
      const errorMessage = await handleApiError(response)
      console.error('Ошибка API:', {
        status: response.status,
        statusText: response.statusText,
        error: errorMessage
      })

      // Если получен 401 Unauthorized или 403 Forbidden, перенаправляем на страницу входа
      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(AUTH_TOKEN_KEY)
        window.location.href = '/'
        throw new Error('Unauthorized')
      }

      throw new Error(errorMessage)
    }

    // Проверяем, что ответ содержит JSON
    const contentType = response.headers.get('content-type')
    if (!contentType?.includes('application/json')) {
      const text = await response.text()
      throw new Error(`Неверный формат ответа: ${text.substring(0, 100)}...`)
    }

    const result = await response.json()

    if (result.errors) {
      // Проверяем ошибки на признаки проблем с авторизацией
      if (hasAuthErrors(result.errors)) {
        localStorage.removeItem(AUTH_TOKEN_KEY)
        window.location.href = '/'
        throw new Error('Unauthorized')
      }

      throw new Error(result.errors[0].message)
    }

    return result.data as T
  } catch (error) {
    console.error('API Error:', error)
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
