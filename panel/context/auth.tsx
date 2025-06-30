import { Component, createContext, createSignal, JSX, useContext } from 'solid-js'
import { query } from '../graphql'
import { ADMIN_LOGIN_MUTATION, ADMIN_LOGOUT_MUTATION } from '../graphql/mutations'
import {
  AUTH_TOKEN_KEY,
  CSRF_TOKEN_KEY,
  checkAuthStatus,
  clearAuthTokens,
  getAuthTokenFromCookie,
  getCsrfTokenFromCookie,
  saveAuthToken
} from '../utils/auth'
/**
 * Модуль авторизации
 * @module auth
 */

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

// Экспортируем утилитарные функции для обратной совместимости
export {
  AUTH_TOKEN_KEY,
  CSRF_TOKEN_KEY,
  getAuthTokenFromCookie,
  getCsrfTokenFromCookie,
  checkAuthStatus,
  clearAuthTokens,
  saveAuthToken
}

interface AuthContextType {
  isAuthenticated: () => boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: () => false,
  login: async () => {},
  logout: async () => {}
})

export const useAuth = () => useContext(AuthContext)

interface AuthProviderProps {
  children: JSX.Element
}

export const AuthProvider: Component<AuthProviderProps> = (props) => {
  console.log('[AuthProvider] Initializing...')
  const [isAuthenticated, setIsAuthenticated] = createSignal(checkAuthStatus())
  console.log(
    `[AuthProvider] Initial auth state: ${isAuthenticated() ? 'authenticated' : 'not authenticated'}`
  )

  const login = async (username: string, password: string) => {
    console.log('[AuthProvider] Attempting login...')
    try {
      const result = await query<{ login: { success: boolean; token?: string } }>(
        `${location.origin}/graphql`,
        ADMIN_LOGIN_MUTATION,
        { email: username, password }
      )

      if (result?.login?.success) {
        console.log('[AuthProvider] Login successful')
        if (result.login.token) {
          saveAuthToken(result.login.token)
        }
        setIsAuthenticated(true)
        // Убираем window.location.href - пусть роутер сам обрабатывает навигацию
      } else {
        console.error('[AuthProvider] Login failed')
        throw new Error('Неверные учетные данные')
      }
    } catch (error) {
      console.error('[AuthProvider] Login error:', error)
      throw error
    }
  }

  const logout = async () => {
    console.log('[AuthProvider] Attempting logout...')
    try {
      const result = await query<{ logout: { success: boolean } }>(
        `${location.origin}/graphql`,
        ADMIN_LOGOUT_MUTATION
      )

      if (result?.logout?.success) {
        console.log('[AuthProvider] Logout successful')
        clearAuthTokens()
        setIsAuthenticated(false)
        window.location.href = '/login'
      }
    } catch (error) {
      console.error('[AuthProvider] Logout error:', error)
      // Даже при ошибке очищаем токены и редиректим
      clearAuthTokens()
      setIsAuthenticated(false)
      window.location.href = '/login'
    }
  }

  const value: AuthContextType = {
    isAuthenticated,
    login,
    logout
  }

  console.log('[AuthProvider] Rendering provider with context')
  return <AuthContext.Provider value={value}>{props.children}</AuthContext.Provider>
}

// Export the logout function for direct use
export const logout = async () => {
  console.log('[Auth] Executing standalone logout...')
  try {
    const result = await query<{ logout: { success: boolean } }>(
      `${location.origin}/graphql`,
      ADMIN_LOGOUT_MUTATION
    )
    console.log('[Auth] Standalone logout result:', result)
    if (result?.logout?.success) {
      clearAuthTokens()
      return true
    }
    return false
  } catch (error) {
    console.error('[Auth] Standalone logout error:', error)
    // Даже при ошибке очищаем токены
    clearAuthTokens()
    throw error
  }
}
