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
    <DataProvider>
      <TableSortProvider>
        <AdminPage apiUrl={`${location.origin}/graphql`} />
      </TableSortProvider>
    </DataProvider>
  )
}
