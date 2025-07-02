import { Route, Router } from '@solidjs/router'
import { lazy, onMount } from 'solid-js'
import { AuthProvider } from './context/auth'
import { I18nProvider } from './intl/i18n'
import LoginPage from './routes/login'

const ProtectedRoute = lazy(() =>
  import('./ui/ProtectedRoute').then((module) => ({ default: module.ProtectedRoute }))
)
/**
 * Корневой компонент приложения
 */
const App = () => {
  console.log('[App] Initializing root component...')

  onMount(() => {
    console.log('[App] Root component mounted')
  })

  return (
    <I18nProvider>
      <AuthProvider>
        <div class="app-container">
          <Router>
            <Route path="/login" component={LoginPage} />
            <Route path="/" component={ProtectedRoute} />
            <Route path="/admin" component={ProtectedRoute} />
            <Route path="/admin/:tab" component={ProtectedRoute} />
          </Router>
        </div>
      </AuthProvider>
    </I18nProvider>
  )
}

export default App
