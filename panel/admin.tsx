/**
 * Компонент страницы администратора
 * @module AdminPage
 */

import { Component, For, Show, createSignal, onMount } from 'solid-js'
import { logout } from './auth'
import { query } from './graphql'

/**
 * Интерфейс для данных пользователя
 */
interface User {
  id: number
  email: string
  name?: string
  slug?: string
  roles: string[]
  created_at?: number
  last_seen?: number
  muted: boolean
  is_active: boolean
}

/**
 * Интерфейс для роли пользователя
 */
interface Role {
  id: number
  name: string
  description?: string
}

/**
 * Интерфейс для ответа API с пользователями
 */
interface AdminGetUsersResponse {
  adminGetUsers: {
    users: User[]
    total: number
    page: number
    perPage: number
    totalPages: number
  }
}

/**
 * Интерфейс для ответа API с ролями
 */
interface AdminGetRolesResponse {
  adminGetRoles: Role[]
}

/**
 * Интерфейс для ответа изменения статуса пользователя
 */
interface AdminSetUserStatusResponse {
  adminSetUserStatus: {
    success: boolean
    error?: string
  }
}

/**
 * Интерфейс для ответа изменения статуса блокировки чата
 */
interface AdminMuteUserResponse {
  adminMuteUser: {
    success: boolean
    error?: string
  }
}

// Интерфейс для пропсов AdminPage
interface AdminPageProps {
  onLogout?: () => void
}

/**
 * Компонент страницы администратора
 */
const AdminPage: Component<AdminPageProps> = (props) => {
  const [activeTab, setActiveTab] = createSignal('users')
  const [users, setUsers] = createSignal<User[]>([])
  const [roles, setRoles] = createSignal<Role[]>([])
  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal<string | null>(null)
  const [selectedUser, setSelectedUser] = createSignal<User | null>(null)
  const [showRolesModal, setShowRolesModal] = createSignal(false)
  const [successMessage, setSuccessMessage] = createSignal<string | null>(null)

  // Параметры пагинации
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

  // Поиск
  const [searchQuery, setSearchQuery] = createSignal('')

  // Периодическая проверка авторизации
  onMount(() => {
    // Загружаем данные при монтировании
    loadUsers()
    loadRoles()
  })

  /**
   * Загрузка списка пользователей с учетом пагинации и поиска
   */
  async function loadUsers() {
    setLoading(true)
    setError(null)

    try {
      const { page, limit } = pagination()
      const offset = (page - 1) * limit
      const search = searchQuery().trim()

      const data = await query<AdminGetUsersResponse>(
        `${location.origin}/graphql`,
        `
        query AdminGetUsers($limit: Int, $offset: Int, $search: String) {
          adminGetUsers(limit: $limit, offset: $offset, search: $search) {
            users {
              id
              email
              name
              slug
              roles
              created_at
              last_seen
              muted
              is_active
            }
            total
            page
            perPage
            totalPages
          }
        }
      `,
        { limit, offset, search: search || null }
      )

      if (data?.adminGetUsers) {
        setUsers(data.adminGetUsers.users)
        setPagination({
          page: data.adminGetUsers.page,
          limit: data.adminGetUsers.perPage,
          total: data.adminGetUsers.total,
          totalPages: data.adminGetUsers.totalPages
        })
      }
    } catch (err) {
      console.error('Ошибка загрузки пользователей:', err)
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка')

      // Если ошибка авторизации - перенаправляем на логин
      if (
        err instanceof Error &&
        (err.message.includes('401') ||
          err.message.includes('авторизации') ||
          err.message.includes('unauthorized') ||
          err.message.includes('Unauthorized'))
      ) {
        handleLogout()
      }
    } finally {
      setLoading(false)
    }
  }

  /**
   * Загрузка списка ролей
   */
  async function loadRoles() {
    try {
      const data = await query<AdminGetRolesResponse>(
        `${location.origin}/graphql`,
        `
        query AdminGetRoles {
          adminGetRoles {
            id
            name
            description
          }
        }
      `
      )

      if (data?.adminGetRoles) {
        setRoles(data.adminGetRoles)
      }
    } catch (err) {
      console.error('Ошибка загрузки ролей:', err)
      // Если ошибка авторизации - перенаправляем на логин
      if (
        err instanceof Error &&
        (err.message.includes('401') ||
          err.message.includes('авторизации') ||
          err.message.includes('unauthorized') ||
          err.message.includes('Unauthorized'))
      ) {
        handleLogout()
      }
    }
  }

  /**
   * Обработчик изменения страницы
   * @param page - Номер страницы
   */
  function handlePageChange(page: number) {
    setPagination({ ...pagination(), page })
    loadUsers()
  }

  /**
   * Обработчик изменения количества элементов на странице
   * @param limit - Количество элементов
   */
  function handlePerPageChange(limit: number) {
    setPagination({ ...pagination(), page: 1, limit })
    loadUsers()
  }

  /**
   * Обработчик изменения поискового запроса
   */
  function handleSearchChange(e: Event) {
    const input = e.target as HTMLInputElement
    setSearchQuery(input.value)
  }

  /**
   * Выполняет поиск
   */
  function handleSearch() {
    setPagination({ ...pagination(), page: 1 })
    loadUsers()
  }

  /**
   * Обработчик нажатия клавиш в поле поиска
   * @param e - Событие клавиатуры
   */
  function handleSearchKeyDown(e: KeyboardEvent) {
    // Если нажат Enter, выполняем поиск
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  /**
   * Блокирует/разблокирует пользователя
   * @param userId - ID пользователя
   * @param isActive - Текущий статус активности
   */
  async function toggleUserBlock(userId: number, isActive: boolean) {
    try {
      setError(null)
      
      // Устанавливаем новый статус (противоположный текущему)
      const newStatus = !isActive
      
      // Выполняем мутацию
      const result = await query<AdminSetUserStatusResponse>(
        `${location.origin}/graphql`,
        `
          mutation AdminSetUserStatus($userId: Int!, $isActive: Boolean!) {
            adminSetUserStatus(userId: $userId, isActive: $isActive) {
              success
              error
            }
          }
        `,
        { userId, isActive: newStatus }
      )
      
      // Проверяем результат
      if (result?.adminSetUserStatus?.success) {
        // Обновляем список пользователей
        setSuccessMessage(`Пользователь ${newStatus ? 'разблокирован' : 'заблокирован'}`)
        
        // Обновляем пользователя в текущем списке
        setUsers(
          users().map((user) => 
            user.id === userId ? { ...user, is_active: newStatus } : user
          )
        )
        
        // Скрываем сообщение через 3 секунды
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(result?.adminSetUserStatus?.error || 'Ошибка обновления статуса пользователя')
      }
    } catch (err) {
      console.error('Ошибка при изменении статуса пользователя:', err)
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка')
    }
  }

  /**
   * Включает/отключает режим блокировки чата для пользователя
   * @param userId - ID пользователя
   * @param isMuted - Текущий статус блокировки чата
   */
  async function toggleUserMute(userId: number, isMuted: boolean) {
    try {
      setError(null)
      
      // Устанавливаем новый статус (противоположный текущему)
      const newMuteStatus = !isMuted
      
      // Выполняем мутацию
      const result = await query<AdminMuteUserResponse>(
        `${location.origin}/graphql`,
        `
          mutation AdminMuteUser($userId: Int!, $muted: Boolean!) {
            adminMuteUser(userId: $userId, muted: $muted) {
              success
              error
            }
          }
        `,
        { userId, muted: newMuteStatus }
      )
      
      // Проверяем результат
      if (result?.adminMuteUser?.success) {
        // Обновляем сообщение об успехе
        setSuccessMessage(`${newMuteStatus ? 'Блокировка' : 'Разблокировка'} чата выполнена`)
        
        // Обновляем пользователя в текущем списке
        setUsers(
          users().map((user) => 
            user.id === userId ? { ...user, muted: newMuteStatus } : user
          )
        )
        
        // Скрываем сообщение через 3 секунды
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(result?.adminMuteUser?.error || 'Ошибка обновления статуса блокировки чата')
      }
    } catch (err) {
      console.error('Ошибка при изменении статуса блокировки чата:', err)
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка')
    }
  }

  /**
   * Закрывает модальное окно ролей
   */
  function closeRolesModal() {
    setShowRolesModal(false)
    setSelectedUser(null)
  }

  /**
   * Обновляет роли пользователя
   * @param userId - ID пользователя
   * @param roles - Новый список ролей
   */
  async function updateUserRoles(userId: number, newRoles: string[]) {
    try {
      await query(
        `${location.origin}/graphql`,
        `
        mutation AdminUpdateUser($userId: Int!, $input: AdminUserUpdateInput!) {
          adminUpdateUser(userId: $userId, input: $input) {
            success
            error
          }
        }
      `,
        {
          userId,
          input: { roles: newRoles }
        }
      )

      // Обновляем роли пользователя в списке
      setUsers((prev) =>
        prev.map((user) => {
          if (user.id === userId) {
            return { ...user, roles: newRoles }
          }
          return user
        })
      )

      // Закрываем модальное окно
      closeRolesModal()

      // Показываем сообщение об успехе
      setSuccessMessage('Роли пользователя успешно обновлены')

      // Скрываем сообщение через 3 секунды
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      console.error('Ошибка обновления ролей:', err)
      setError(err instanceof Error ? err.message : 'Ошибка обновления ролей')
    }
  }

  /**
   * Выход из системы
   */
  function handleLogout() {
    // Сначала выполняем локальные действия по очистке данных
    setUsers([])
    setRoles([])

    // Затем выполняем выход
    logout(() => {
      // Вызываем коллбэк для оповещения родителя о выходе
      if (props.onLogout) {
        props.onLogout()
      }
    })
  }

  /**
   * Форматирование даты
   * @param timestamp - Временная метка
   */
  function formatDate(timestamp?: number): string {
    if (!timestamp) return 'Н/Д'
    return new Date(timestamp * 1000).toLocaleString('ru')
  }

  /**
   * Формирует массив номеров страниц для отображения в пагинации
   * @returns Массив номеров страниц
   */
  function getPageNumbers(): number[] {
    const result: number[] = []
    const maxVisible = 5 // Максимальное количество видимых номеров страниц

    const paginationData = pagination()
    const currentPage = paginationData.page
    const totalPages = paginationData.totalPages

    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2))
    const endPage = Math.min(totalPages, startPage + maxVisible - 1)

    // Если endPage достиг предела, сдвигаем startPage назад
    if (endPage - startPage + 1 < maxVisible && startPage > 1) {
      startPage = Math.max(1, endPage - maxVisible + 1)
    }

    // Генерируем номера страниц
    for (let i = startPage; i <= endPage; i++) {
      result.push(i)
    }

    return result
  }

  /**
   * Компонент пагинации
   */
  const Pagination: Component = () => {
    const paginationData = pagination()
    const currentPage = paginationData.page
    const total = paginationData.totalPages

    return (
      <div class="pagination">
        <div class="pagination-info">
          Показано {users().length} из {paginationData.total} пользователей
        </div>
        <div class="pagination-controls">
          <button
            class="pagination-button"
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1}
          >
            &laquo;
          </button>

          <For each={getPageNumbers()}>
            {(page) =>
              typeof page === 'number' ? (
                <button
                  class={`pagination-button ${page === currentPage ? 'active' : ''}`}
                  onClick={() => handlePageChange(page)}
                >
                  {page}
                </button>
              ) : (
                <span class="pagination-ellipsis">{page}</span>
              )
            }
          </For>

          <button
            class="pagination-button"
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage === total}
          >
            &raquo;
          </button>
        </div>
        <div class="pagination-per-page">
          <label>
            Записей на странице:
            <select
              value={paginationData.limit}
              onChange={(e) => handlePerPageChange(Number.parseInt(e.target.value))}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </label>
        </div>
      </div>
    )
  }

  /**
   * Компонент модального окна для управления ролями
   */
  const RolesModal: Component = () => {
    const user = selectedUser()
    const [selectedRoles, setSelectedRoles] = createSignal<string[]>(user ? [...user.roles] : [])

    const toggleRole = (role: string) => {
      const current = selectedRoles()
      if (current.includes(role)) {
        setSelectedRoles(current.filter((r) => r !== role))
      } else {
        setSelectedRoles([...current, role])
      }
    }

    const saveRoles = () => {
      if (user) {
        updateUserRoles(user.id, selectedRoles())
      }
    }

    if (!user) return null

    return (
      <div class="modal-overlay">
        <div class="modal-content">
          <h2>Управление ролями пользователя</h2>
          <p>Пользователь: {user.email}</p>

          <div class="roles-list">
            <For each={roles()}>
              {(role) => (
                <div class="role-item">
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedRoles().includes(role.name)}
                      onChange={() => toggleRole(role.name)}
                    />
                    {role.name}
                  </label>
                  <Show when={role.description}>
                    <p class="role-description">{role.description}</p>
                  </Show>
                </div>
              )}
            </For>
          </div>

          <div class="modal-actions">
            <button class="cancel-button" onClick={closeRolesModal}>
              Отмена
            </button>
            <button class="save-button" onClick={saveRoles}>
              Сохранить
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div class="admin-page">
      <header>
        <div class="header-container">
          <h1>Панель администратора</h1>
          <button class="logout-button" onClick={handleLogout}>
            Выйти
          </button>
        </div>

        <nav class="admin-tabs">
          <button class={activeTab() === 'users' ? 'active' : ''} onClick={() => setActiveTab('users')}>
            Пользователи
          </button>
        </nav>
      </header>

      <main>
        <Show when={error()}>
          <div class="error-message">{error()}</div>
        </Show>

        <Show when={successMessage()}>
          <div class="success-message">{successMessage()}</div>
        </Show>

        <Show when={loading()}>
          <div class="loading">Загрузка данных...</div>
        </Show>

        <Show when={!loading() && users().length === 0 && !error()}>
          <div class="empty-state">Нет данных для отображения</div>
        </Show>

        <Show when={!loading() && users().length > 0}>
          <div class="users-controls">
            <div class="search-container">
              <div class="search-input-group">
                <input
                  type="text"
                  placeholder="Поиск по email, имени или ID..."
                  value={searchQuery()}
                  onInput={handleSearchChange}
                  onKeyDown={handleSearchKeyDown}
                  class="search-input"
                />
                <button class="search-button" onClick={handleSearch}>
                  Поиск
                </button>
              </div>
            </div>
          </div>

          <div class="users-list">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Email</th>
                  <th>Имя</th>
                  <th>Роли</th>
                  <th>Создан</th>
                  <th>Последний вход</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                <For each={users()}>
                  {(user) => (
                    <tr class={user.is_active ? '' : 'blocked'}>
                      <td>{user.id}</td>
                      <td>{user.email}</td>
                      <td>{user.name || '-'}</td>
                      <td>{user.roles.join(', ') || '-'}</td>
                      <td>{formatDate(user.created_at)}</td>
                      <td>{formatDate(user.last_seen)}</td>
                      <td>
                        <span class={`status ${user.is_active ? 'active' : 'inactive'}`}>
                          {user.is_active ? 'Активен' : 'Заблокирован'}
                        </span>
                      </td>
                      <td class="actions">
                        <button
                          class={user.is_active ? 'block' : 'unblock'}
                          onClick={() => toggleUserBlock(user.id, user.is_active)}
                        >
                          {user.is_active ? 'Блокировать' : 'Разблокировать'}
                        </button>
                        <button
                          class={user.muted ? 'unmute' : 'mute'}
                          onClick={() => toggleUserMute(user.id, user.muted)}
                        >
                          {user.muted ? 'Unmute' : 'Mute'}
                        </button>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>

          <Pagination />
        </Show>
      </main>

      <Show when={showRolesModal()}>
        <RolesModal />
      </Show>
    </div>
  )
}

export default AdminPage
