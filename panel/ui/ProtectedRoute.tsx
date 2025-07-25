import { createEffect, Show } from 'solid-js'
import { useAuth } from '../context/auth'
import { DataProvider } from '../context/data'
import { TableSortProvider } from '../context/sort'
import AdminPage from '../routes/admin'

/**
 * Компонент защищенного маршрута
 */
export const ProtectedRoute = () => {
  const auth = useAuth()

  createEffect(() => {
    if (auth.isReady() && !auth.isAuthenticated()) {
      window.location.href = '/login'
    }
  })

  return (
    <Show
      when={auth.isReady()}
      fallback={
        <div class="loading-screen">
          <div class="loading-spinner" />
          <div>Инициализация авторизации...</div>
        </div>
      }
    >
      <Show
        when={auth.isAuthenticated()}
        fallback={
          <div class="loading-screen">
            <div class="loading-spinner" />
            <div>Перенаправление на страницу входа...</div>
          </div>
        }
      >
        <DataProvider>
          <TableSortProvider>
            <AdminPage apiUrl={`${location.origin}/graphql`} />
          </TableSortProvider>
        </DataProvider>
      </Show>
    </Show>
  )
}
