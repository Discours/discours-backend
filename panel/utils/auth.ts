/**
 * Утилиты для работы с токенами авторизации
 * @module auth-utils
 */

// Экспортируем константы для использования в других модулях
export const AUTH_TOKEN_KEY = 'auth_token'
export const CSRF_TOKEN_KEY = 'csrf_token'

/**
 * Получает токен авторизации из cookie
 * @returns Токен или пустую строку, если токен не найден
 */
export function getAuthTokenFromCookie(): string {
  console.log('[Auth] Checking auth token in cookies...')
  const cookieItems = document.cookie.split(';')
  for (const item of cookieItems) {
    const [name, value] = item.trim().split('=')
    if (name === AUTH_TOKEN_KEY) {
      console.log('[Auth] Found auth token in cookies')
      return value
    }
  }
  console.log('[Auth] No auth token found in cookies')
  return ''
}

/**
 * Получает CSRF-токен из cookie
 * @returns CSRF-токен или пустую строку, если токен не найден
 */
export function getCsrfTokenFromCookie(): string {
  console.log('[Auth] Checking CSRF token in cookies...')
  const cookieItems = document.cookie.split(';')
  for (const item of cookieItems) {
    const [name, value] = item.trim().split('=')
    if (name === CSRF_TOKEN_KEY) {
      console.log('[Auth] Found CSRF token in cookies')
      return value
    }
  }
  console.log('[Auth] No CSRF token found in cookies')
  return ''
}

/**
 * Очищает все токены авторизации
 */
export function clearAuthTokens(): void {
  console.log('[Auth] Clearing all auth tokens...')
  // Очищаем токен из localStorage
  localStorage.removeItem(AUTH_TOKEN_KEY)

  // Для удаления cookie устанавливаем ей истекшее время жизни
  // biome-ignore lint/suspicious/noDocumentCookie: Требуется для кроссбраузерной совместимости
  document.cookie = `${AUTH_TOKEN_KEY}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
  // biome-ignore lint/suspicious/noDocumentCookie: Требуется для кроссбраузерной совместимости
  document.cookie = `${CSRF_TOKEN_KEY}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
  console.log('[Auth] Auth tokens cleared')
}

/**
 * Сохраняет токен авторизации
 * @param token - Токен для сохранения
 */
export function saveAuthToken(token: string): void {
  console.log('[Auth] Attempting to save auth token...')
  if (!token) {
    console.log('[Auth] No token provided, skipping save')
    return
  }

  // Всегда сохраняем токен в localStorage для надежности
  localStorage.setItem(AUTH_TOKEN_KEY, token)
  console.log('[Auth] Token saved to localStorage')
}

/**
 * Проверяет, авторизован ли пользователь
 * @returns Статус авторизации
 */
export function checkAuthStatus(): boolean {
  console.log('[Auth] Checking authentication status...')

  // Проверяем наличие cookie auth_token
  const cookieToken = getAuthTokenFromCookie()
  const hasCookie = !!cookieToken && cookieToken.length > 10

  // Проверяем наличие токена в localStorage
  const localToken = localStorage.getItem(AUTH_TOKEN_KEY)
  const hasLocalToken = !!localToken && localToken.length > 10

  const isAuth = hasCookie || hasLocalToken
  console.log(`[Auth] Cookie token: ${hasCookie ? 'present' : 'missing'}`)
  console.log(`[Auth] Local token: ${hasLocalToken ? 'present' : 'missing'}`)
  console.log(`[Auth] Authentication status: ${isAuth ? 'authenticated' : 'not authenticated'}`)

  return isAuth
}
