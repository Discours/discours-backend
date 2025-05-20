import { Component, Show, Suspense, createSignal, lazy, onMount, createEffect } from 'solid-js'
import { isAuthenticated, getAuthTokenFromCookie } from './auth'

// Ленивая загрузка компонентов
const AdminPage = lazy(() => import('./admin'))
const LoginPage = lazy(() => import('./login'))

/**
 * Корневой компонент приложения с простой логикой отображения
 */
const App: Component = () => {
  const [authenticated, setAuthenticated] = createSignal<boolean | null>(null)
  const [loading, setLoading] = createSignal(true)
  const [checkingAuth, setCheckingAuth] = createSignal(true)

  // Проверяем авторизацию при монтировании
  onMount(() => {
    checkAuthentication()
  })

  // Периодическая проверка авторизации
  createEffect(() => {
    const authCheckInterval = setInterval(() => {
      // Перепроверяем статус авторизации каждые 60 секунд
      if (!checkingAuth()) {
        const authed = isAuthenticated()
        if (!authed && authenticated()) {
          console.log('Сессия истекла, требуется повторная авторизация')
          setAuthenticated(false)
        }
      }
    }, 60000)

    return () => clearInterval(authCheckInterval)
  })

  // Функция проверки авторизации
  const checkAuthentication = async () => {
    setCheckingAuth(true)
    setLoading(true)
    
    try {
      // Проверяем состояние авторизации
      const authed = isAuthenticated()
      
      // Если токен есть, но он невалидный, авторизация не удалась
      if (authed) {
        const token = getAuthTokenFromCookie() || localStorage.getItem('auth_token')
        if (!token || token.length < 10) {
          setAuthenticated(false)
        } else {
          setAuthenticated(true)
        }
      } else {
        setAuthenticated(false)
      }
    } catch (error) {
      console.error('Ошибка при проверке авторизации:', error)
      setAuthenticated(false)
    } finally {
      setLoading(false)
      setCheckingAuth(false)
    }
  }

  // Обработчик успешной авторизации
  const handleLoginSuccess = () => {
    setAuthenticated(true)
  }

  // Обработчик выхода из системы
  const handleLogout = () => {
    setAuthenticated(false)
  }

  return (
    <div class="app-container">
      <Suspense
        fallback={
          <div class="loading-screen">
            <div class="loading-spinner" />
            <h2>Загрузка компонентов...</h2>
          </div>
        }
      >
        <Show
          when={!loading()}
          fallback={
            <div class="loading-screen">
              <div class="loading-spinner" />
              <h2>Проверка авторизации...</h2>
            </div>
          }
        >
          {authenticated() ? (
            <AdminPage apiUrl={`${location.origin}/graphql`} onLogout={handleLogout} />
          ) : (
            <LoginPage onLoginSuccess={handleLoginSuccess} />
          )}
        </Show>
      </Suspense>
    </div>
  )
}

export default App
