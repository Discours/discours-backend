import { Component, Show, Suspense, createSignal, lazy, onMount } from 'solid-js'
import { isAuthenticated } from './auth'

// Ленивая загрузка компонентов
const AdminPage = lazy(() => import('./admin'))
const LoginPage = lazy(() => import('./login'))

/**
 * Корневой компонент приложения с простой логикой отображения
 */
const App: Component = () => {
  const [authenticated, setAuthenticated] = createSignal<boolean | null>(null)
  const [loading, setLoading] = createSignal(true)

  // Проверяем авторизацию при монтировании
  onMount(() => {
    const authed = isAuthenticated()
    setAuthenticated(authed)
    setLoading(false)
  })

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
            <h2>Загрузка...</h2>
          </div>
        }
      >
        <Show
          when={!loading()}
          fallback={
            <div class="loading-screen">
              <div class="loading-spinner" />
              <h2>Загрузка...</h2>
            </div>
          }
        >
          {authenticated() ? (
            <AdminPage onLogout={handleLogout} />
          ) : (
            <LoginPage onLoginSuccess={handleLoginSuccess} />
          )}
        </Show>
      </Suspense>
    </div>
  )
}

export default App
