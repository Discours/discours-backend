import { useAuth } from '../context/auth'
import { DataProvider } from '../context/data'
import { TableSortProvider } from '../context/sort'
import AdminPage from '../routes/admin'

/**
 * Компонент защищенного маршрута
 */
export const ProtectedRoute = () => {
  console.log('[ProtectedRoute] Checking authentication...')
  const auth = useAuth()
  const isReady = auth.isReady()
  const authenticated = auth.isAuthenticated()

  console.log(`[ProtectedRoute] Auth state: ready=${isReady}, authenticated=${authenticated}`)

  // Если авторизация еще не готова, показываем загрузку
  if (!isReady) {
    console.log('[ProtectedRoute] Auth not ready, showing loading...')
    return (
      <div class="loading-screen">
        <div class="loading-spinner" />
        <div>Инициализация авторизации...</div>
      </div>
    )
  }

  // Если авторизация готова, но пользователь не аутентифицирован
  if (!authenticated) {
    console.log('[ProtectedRoute] Not authenticated, redirecting to login...')
    // Используем window.location.href для редиректа
    window.location.href = '/login'
    return (
      <div class="loading-screen">
        <div class="loading-spinner" />
        <div>Перенаправление на страницу входа...</div>
      </div>
    )
  }

  console.log('[ProtectedRoute] Auth ready and authenticated, rendering admin panel...')
  return (
    <DataProvider>
      <TableSortProvider>
        <AdminPage apiUrl={`${location.origin}/graphql`} />
      </TableSortProvider>
    </DataProvider>
  )
}
