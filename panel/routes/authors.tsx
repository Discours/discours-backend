import { Component, createSignal, For, onMount, Show } from 'solid-js'
import type { AuthorsSortField } from '../context/sort'
import { AUTHORS_SORT_CONFIG } from '../context/sortConfig'
import { query } from '../graphql'
import type { Query, AdminUserInfo as User } from '../graphql/generated/schema'
import { ADMIN_UPDATE_USER_MUTATION } from '../graphql/mutations'
import { ADMIN_GET_USERS_QUERY } from '../graphql/queries'
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
  console.log('[AuthorsRoute] Initializing...')
  const [authors, setUsers] = createSignal<User[]>([])
  const [loading, setLoading] = createSignal(true)
  const [selectedUser, setSelectedUser] = createSignal<User | null>(null)
  const [showEditModal, setShowEditModal] = createSignal(false)

  // Pagination state
  const [pagination, setPagination] = createSignal<{
    page: number
    limit: number
    total: number
    totalPages: number
  }>({
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
    console.log('[AuthorsRoute] Loading authors...')
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
        console.log('[AuthorsRoute] Users loaded:', data.adminGetUsers.authors.length)
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
  async function updateUser(userData: {
    id: number
    email?: string
    name?: string
    slug?: string
    roles: string[]
  }) {
    try {
      await query(`${location.origin}/graphql`, ADMIN_UPDATE_USER_MUTATION, {
        user: userData
      })

      setUsers((prev) =>
        prev.map((user) => {
          if (user.id === userData.id) {
            return {
              ...user,
              email: userData.email || user.email,
              name: userData.name || user.name,
              slug: userData.slug || user.slug,
              roles: userData.roles
            }
          }
          return user
        })
      )

      closeEditModal()
      props.onSuccess?.('Данные пользователя успешно обновлены')
      void loadUsers()
    } catch (err) {
      console.error('Ошибка обновления пользователя:', err)
      let errorMessage = err instanceof Error ? err.message : 'Ошибка обновления данных пользователя'

      if (errorMessage.includes('author_role.community')) {
        errorMessage = 'Ошибка: для роли author требуется указать community. Обратитесь к администратору.'
      }

      props.onError?.(errorMessage)
    }
  }

  function closeEditModal() {
    setShowEditModal(false)
    setSelectedUser(null)
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

  // Search handlers
  function handleSearchChange(value: string) {
    setSearchQuery(value)
  }

  function handleSearch() {
    setPagination((prev) => ({ ...prev, page: 1 }))
    void loadUsers()
  }

  // Load authors on mount
  onMount(() => {
    console.log('[AuthorsRoute] Component mounted, loading authors...')
    void loadUsers()
  })

  /**
   * Компонент для отображения роли с эмоджи и тултипом
   */
  const RoleBadge: Component<{ role: string }> = (props) => {
    const getRoleIcon = (role: string): string => {
      switch (role.toLowerCase().trim()) {
        case 'администратор':
        case 'admin':
          return '🪄'
        case 'редактор':
        case 'editor':
          return '✒️'
        case 'эксперт':
        case 'expert':
          return '🔬'
        case 'автор':
        case 'author':
          return '📝'
        case 'читатель':
        case 'reader':
          return '📖'
        case 'banned':
        case 'заблокирован':
          return '🚫'
        case 'verified':
        case 'проверен':
          return '✓'
        default:
          return '🎭'
      }
    }

    return (
      <span title={props.role} style={{ 'margin-right': '0.25rem' }}>
        {getRoleIcon(props.role)}
      </span>
    )
  }

  return (
    <div class={styles['authors-container']}>
      <Show when={loading()}>
        <div class={styles['loading']}>Загрузка данных...</div>
      </Show>

      <Show when={!loading() && authors().length === 0}>
        <div class={styles['empty-state']}>Нет данных для отображения</div>
      </Show>

      <Show when={!loading() && authors().length > 0}>
        <TableControls
          searchValue={searchQuery()}
          onSearchChange={handleSearchChange}
          onSearch={handleSearch}
          searchPlaceholder="Поиск по email, имени или ID..."
          isLoading={loading()}
        />

        <div class={styles['authors-list']}>
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
              <For each={authors()}>
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
                        <For each={Array.from(user.roles || []).filter(Boolean)}>
                          {(role) => <RoleBadge role={role} />}
                        </For>
                        {/* Показываем сообщение если ролей нет */}
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
        </div>

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
          onClose={closeEditModal}
          onSave={updateUser}
        />
      </Show>
    </div>
  )
}

export default AuthorsRoute
