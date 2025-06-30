import { Route, Router } from '@solidjs/router'
import { lazy, onMount, Suspense } from 'solid-js'
import { AuthProvider, useAuth } from './context/auth'

// Ленивая загрузка компонентов
const AdminPage = lazy(() => {
  console.log('[App] Loading AdminPage component...')
  return import('./admin')
})
const LoginPage = lazy(() => {
  console.log('[App] Loading LoginPage component...')
  return import('./routes/login')
})

/**
 * Компонент защищенного маршрута
 */
const ProtectedRoute = () => {
  console.log('[ProtectedRoute] Checking authentication...')
  const auth = useAuth()
  const authenticated = auth.isAuthenticated()
  console.log(
    `[ProtectedRoute] Authentication state: ${authenticated ? 'authenticated' : 'not authenticated'}`
  )

  if (!authenticated) {
    console.log('[ProtectedRoute] Not authenticated, redirecting to login...')
    // Используем window.location.href для редиректа
    window.location.href = '/login'
    return (
      <div class="loading-screen">
        <div class="loading-spinner" />
        <div>Проверка авторизации...</div>
      </div>
    )
  }

  return (
    <Suspense
      fallback={
        <div class="loading-screen">
          <div class="loading-spinner" />
          <div>Загрузка админ-панели...</div>
        </div>
      }
    >
      <AdminPage apiUrl={`${location.origin}/graphql`} />
    </Suspense>
  )
}

/**
 * Корневой компонент приложения
 */
const App = () => {
  console.log('[App] Initializing root component...')

  onMount(() => {
    console.log('[App] Root component mounted')
  })

  return (
    <AuthProvider>
      <div class="app-container">
        <Router>
          <Route
            path="/login"
            component={() => (
              <Suspense
                fallback={
                  <div class="loading-screen">
                    <div class="loading-spinner" />
                    <div>Загрузка страницы входа...</div>
                  </div>
                }
              >
                <LoginPage />
              </Suspense>
            )}
          />
          <Route path="/" component={ProtectedRoute} />
          <Route path="/admin" component={ProtectedRoute} />
          <Route path="/admin/:tab" component={ProtectedRoute} />
        </Router>
      </div>
    </AuthProvider>
  )
}

export default App
