import { Component, createSignal, For, onMount, Show } from 'solid-js'
import { query } from '../graphql'
import type { Query, AdminUserInfo as User } from '../graphql/generated/schema'
import { ADMIN_UPDATE_USER_MUTATION } from '../graphql/mutations'
import { ADMIN_GET_USERS_QUERY } from '../graphql/queries'
import UserEditModal from '../modals/RolesModal'
import styles from '../styles/Admin.module.css'
import Pagination from '../ui/Pagination'
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
    limit: 10,
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
      props.onError?.(error instanceof Error ? error.message : 'Failed to load authors')
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
  function handleSearchChange(e: Event) {
    const input = e.target as HTMLInputElement
    setSearchQuery(input.value)
  }

  function handleSearch() {
    setPagination((prev) => ({ ...prev, page: 1 }))
    void loadUsers()
  }

  function handleSearchKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  // Load authors on mount
  onMount(() => {
    console.log('[AuthorsRoute] Component mounted, loading authors...')
    void loadUsers()
  })

  /**
   * Компонент для отображения роли с иконкой
   */
  const RoleBadge: Component<{ role: string }> = (props) => {
    const getRoleIcon = (role: string): string => {
      switch (role.toLowerCase()) {
        case 'admin':
          return '👑'
        case 'editor':
          return '✏️'
        case 'expert':
          return '🎓'
        case 'author':
          return '📝'
        case 'reader':
          return '👤'
        case 'banned':
          return '🚫'
        case 'verified':
          return '✓'
        default:
          return '👤'
      }
    }

    return (
      <span class="role-badge" title={props.role}>
        <span class="role-icon">{getRoleIcon(props.role)}</span>
        <span class="role-name">{props.role}</span>
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
        <div class={styles['authors-controls']}>
          <div class={styles['search-container']}>
            <div class={styles['search-input-group']}>
              <input
                type="text"
                placeholder="Поиск по email, имени или ID..."
                value={searchQuery()}
                onInput={handleSearchChange}
                onKeyDown={handleSearchKeyDown}
                class={styles['search-input']}
              />
              <button class={styles['search-button']} onClick={handleSearch}>
                Поиск
              </button>
            </div>
          </div>
        </div>

        <div class={styles['authors-list']}>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Email</th>
                <th>Имя</th>
                <th>Создан</th>
                <th>Роли</th>
              </tr>
            </thead>
            <tbody>
              <For each={authors()}>
                {(user) => (
                  <tr>
                    <td>{user.id}</td>
                    <td>{user.email}</td>
                    <td>{user.name || '-'}</td>
                    <td>{formatDateRelative(user.created_at || Date.now())}</td>
                    <td class={styles['roles-cell']}>
                      <div class={styles['roles-container']}>
                        <For each={Array.from(user.roles || []).filter(Boolean)}>
                          {(role) => <RoleBadge role={role} />}
                        </For>
                        <div
                          class={styles['role-badge edit-role-badge']}
                          onClick={() => {
                            setSelectedUser(user)
                            setShowEditModal(true)
                          }}
                        >
                          <span class={styles['role-icon']}>🎭</span>
                        </div>
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
