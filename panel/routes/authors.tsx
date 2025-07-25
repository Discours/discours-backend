import { Component, createSignal, For, onMount, Show } from 'solid-js'
import type { AuthorsSortField } from '../context/sort'
import { AUTHORS_SORT_CONFIG } from '../context/sortConfig'
import { query } from '../graphql'
import type { Query, AdminUserInfo as User } from '../graphql/generated/schema'
import { ADMIN_GET_USERS_QUERY, ADMIN_UPDATE_USER_MUTATION } from '../graphql/queries'
import UserEditModal from '../modals/RolesModal'
import styles from '../styles/Admin.module.css'
import Pagination from '../ui/Pagination'
import SortableHeader from '../ui/SortableHeader'
import TableControls from '../ui/TableControls'
import { formatDateRelative } from '../utils/date'

export interface AuthorsRouteProps {
  onError?: (error: string) => void
  onSuccess?: (message: string) => void
}

const AuthorsRoute: Component<AuthorsRouteProps> = (props) => {
  const [users, setUsers] = createSignal<User[]>([])
  const [loading, setLoading] = createSignal(true)
  const [selectedUser, setSelectedUser] = createSignal<User | null>(null)
  const [showEditModal, setShowEditModal] = createSignal(false)

  // Pagination state
  const [pagination, setPagination] = createSignal({
    page: 1,
    limit: 20,
    total: 0,
    totalPages: 1
  })

  // Search state
  const [searchQuery, setSearchQuery] = createSignal('')

  /**
   * Загрузка списка пользователей с учетом пагинации и поиска
   */
  async function loadUsers() {
    try {
      setLoading(true)
      const data = await query<{ adminGetUsers: Query['adminGetUsers'] }>(
        `${location.origin}/graphql`,
        ADMIN_GET_USERS_QUERY,
        {
          search: searchQuery(),
          limit: pagination().limit,
          offset: (pagination().page - 1) * pagination().limit
        }
      )
      if (data?.adminGetUsers?.authors) {
        setUsers(data.adminGetUsers.authors)
        setPagination((prev) => ({
          ...prev,
          total: data.adminGetUsers.total || 0,
          totalPages: data.adminGetUsers.totalPages || 1
        }))
      }
    } catch (error) {
      console.error('[AuthorsRoute] Failed to load authors:', error)
      props.onError?.(error instanceof Error ? error.message : 'Не удалось загрузить список пользователей')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Обновляет данные пользователя (профиль и роли)
   */
  const updateUser = async (userData: {
    id: number
    email?: string
    name?: string
    slug?: string
    roles: string
  }) => {
    try {
      const result = await query<{
        updateUser: User
      }>(`${location.origin}/graphql`, ADMIN_UPDATE_USER_MUTATION, {
        ...userData,
        roles: userData.roles
      })

      if (result.updateUser) {
        // Обновляем локальный список пользователей
        setUsers((prevUsers) =>
          prevUsers.map((user) => (user.id === result.updateUser.id ? result.updateUser : user))
        )
        // Закрываем модальное окно
        setShowEditModal(false)
      }
    } catch (error) {
      console.error('Ошибка при обновлении пользователя:', error)
      props.onError?.(error instanceof Error ? error.message : 'Не удалось обновить пользователя')
    }
  }

  // Pagination handlers
  function handlePageChange(page: number) {
    setPagination((prev) => ({ ...prev, page }))
    void loadUsers()
  }

  function handlePerPageChange(limit: number) {
    setPagination((prev) => ({ ...prev, page: 1, limit }))
    void loadUsers()
  }

  function handleSearch() {
    setPagination((prev) => ({ ...prev, page: 1 }))
    void loadUsers()
  }

  // Load authors on mount
  onMount(() => {
    void loadUsers()
  })

  /**
   * Компонент для отображения роли с эмоджи и тултипом
   */
  const RoleBadge: Component<{ role: string }> = (props) => {
    const getRoleIcon = (role: string): string => {
      switch (role.toLowerCase().trim()) {
        case 'admin':
          return '🔧'
        case 'editor':
          return '✒️'
        case 'expert':
          return '🔬'
        case 'author':
          return '📝'
        case 'reader':
          return '📖'
        default:
          return '👤'
      }
    }

    return <span title={props.role}>{getRoleIcon(props.role)}</span>
  }

  return (
    <div class={styles['authors-container']}>
      <Show when={loading()}>
        <div class={styles['loading']}>Загрузка данных...</div>
      </Show>

      <Show when={!loading() && users().length === 0}>
        <div class={styles['empty-state']}>Нет данных для отображения</div>
      </Show>

      <Show when={!loading() && users().length > 0}>
        <TableControls
          searchValue={searchQuery()}
          onSearchChange={setSearchQuery}
          onSearch={handleSearch}
          searchPlaceholder="Поиск по email, имени или ID..."
        />

        <table>
          <thead>
            <tr>
              <SortableHeader
                field={'id' as AuthorsSortField}
                allowedFields={AUTHORS_SORT_CONFIG.allowedFields}
              >
                ID
              </SortableHeader>
              <SortableHeader
                field={'email' as AuthorsSortField}
                allowedFields={AUTHORS_SORT_CONFIG.allowedFields}
              >
                Email
              </SortableHeader>
              <SortableHeader
                field={'name' as AuthorsSortField}
                allowedFields={AUTHORS_SORT_CONFIG.allowedFields}
              >
                Имя
              </SortableHeader>
              <SortableHeader
                field={'created_at' as AuthorsSortField}
                allowedFields={AUTHORS_SORT_CONFIG.allowedFields}
              >
                Создан
              </SortableHeader>
              <th>Роли</th>
            </tr>
          </thead>
          <tbody>
            <For each={users()}>
              {(user) => (
                <tr
                  onClick={() => {
                    setSelectedUser(user)
                    setShowEditModal(true)
                  }}
                >
                  <td>{user.id}</td>
                  <td>{user.email}</td>
                  <td>{user.name || '-'}</td>
                  <td>{formatDateRelative(user.created_at || Date.now())()}</td>
                  <td class={styles['roles-cell']}>
                    <div class={styles['roles-container']}>
                      <For each={user.roles || []}>{(role) => <RoleBadge role={role.trim()} />}</For>
                      {(!user.roles || user.roles.length === 0) && (
                        <span style="color: #999; font-size: 0.875rem;">Нет ролей</span>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>

        <Pagination
          currentPage={pagination().page}
          totalPages={pagination().totalPages}
          total={pagination().total}
          limit={pagination().limit}
          onPageChange={handlePageChange}
          onPerPageChange={handlePerPageChange}
        />
      </Show>

      <Show when={showEditModal() && selectedUser()}>
        <UserEditModal
          user={selectedUser()!}
          isOpen={showEditModal()}
          onClose={() => setShowEditModal(false)}
          onSave={updateUser}
        />
      </Show>
    </div>
  )
}

export default AuthorsRoute
