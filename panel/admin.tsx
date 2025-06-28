/**
 * Компонент страницы администратора
 * @module AdminPage
 */

import { Component, For, Show, createSignal, onMount, createEffect } from 'solid-js'
import { logout } from './auth'
import { query } from './graphql'
import Prism from 'prismjs'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-markup'
import 'prismjs/themes/prism-tomorrow.css'

// Определяем GraphQL запрос
const ADMIN_GET_SHOUTS_QUERY = `
  query AdminGetShouts($limit: Int, $offset: Int, $status: String) {
    adminGetShouts(limit: $limit, offset: $offset, status: $status) {
      shouts {
        id
        title
        slug
        body
        lead
        subtitle
        layout
        lang
        cover
        cover_caption
        media {
          url
          title
          body
          source
          pic
          date
          genre
          artist
          lyrics
        }
        seo
        created_at
        updated_at
        published_at
        featured_at
        deleted_at
        created_by {
          id
          email
          name
        }
        authors {
          id
          email
          name
          slug
        }
        topics {
          id
          title
          slug
        }
        version_of
        draft
      }
      total
      page
      perPage
      totalPages
    }
  }
`

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
}

/**
 * Интерфейс для роли пользователя
 */
interface Role {
  id: string  // ID роли - строка, не число
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
 * Интерфейс для ответа обновления пользователя
 */
interface AdminUpdateUserResponse {
  success: boolean
  error?: string
}

/**
 * Интерфейс для входных данных обновления пользователя
 */
interface AdminUserUpdateInput {
  id: number
  roles: string[]
  community?: number
}

/**
 * Интерфейс для переменной окружения
 */
interface EnvVariable {
  key: string
  value: string
  description?: string
  type: string
  isSecret: boolean
}

/**
 * Интерфейс для секции переменных окружения
 */
interface EnvSection {
  name: string
  description?: string
  variables: EnvVariable[]
}

/**
 * Интерфейс для публикации
 */
interface Shout {
  id: number
  title: string
  slug: string
  body: string
  lead?: string
  subtitle?: string
  layout: string
  lang: string
  cover?: string
  cover_caption?: string
  media?: any[]
  seo?: string
  created_at: number
  updated_at?: number
  published_at?: number
  featured_at?: number
  deleted_at?: number
  created_by: {
    id: number
    email?: string
    name?: string
  }
  updated_by?: {
    id: number
    email?: string
    name?: string
  }
  deleted_by?: {
    id: number
    email?: string
    name?: string
  }
  community: {
    id: number
    name?: string
  }
  authors?: Array<{
    id: number
    email?: string
    name?: string
    slug?: string
  }>
  topics?: Array<{
    id: number
    title?: string
    slug?: string
  }>
  version_of?: number
  draft?: number
  stat?: any
}

/**
 * Интерфейс для ответа API с публикациями
 */
interface AdminGetShoutsData {
  adminGetShouts: {
    shouts: any[]
    total: number
    page: number
    perPage: number
    totalPages: number
  }
}

/**
 * Интерфейс свойств компонента AdminPage
 */
interface AdminPageProps {
  apiUrl: string
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
  const [showBodyModal, setShowBodyModal] = createSignal(false)
  const [selectedShoutBody, setSelectedShoutBody] = createSignal<string>('')
  const [showMediaBodyModal, setShowMediaBodyModal] = createSignal(false)
  const [selectedMediaBody, setSelectedMediaBody] = createSignal<string>('')

  // Переменные среды
  const [envSections, setEnvSections] = createSignal<EnvSection[]>([])
  const [envLoading, setEnvLoading] = createSignal(false)
  const [editingVariable, setEditingVariable] = createSignal<EnvVariable | null>(null)
  const [showVariableModal, setShowVariableModal] = createSignal(false)

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

  // Публикации
  const [shouts, setShouts] = createSignal<Shout[]>([])
  const [shoutsLoading, setShoutsLoading] = createSignal(false)
  const [shoutsStatus, setShoutsStatus] = createSignal('all') // all, published, draft, deleted
  const [shoutsPagination, setShoutsPagination] = createSignal<{
    page: number
    limit: number
    total: number
    totalPages: number
  }>({
    page: 1,
    limit: 20,
    total: 0,
    totalPages: 0
  })
  const [shoutsSearchQuery, setShoutsSearchQuery] = createSignal('')

  /**
   * Загрузка списка пользователей с учетом пагинации и поиска
   */
  async function loadUsers() {
    setLoading(true)
    setError(null)

    try {
      // Используем актуальные данные из состояния
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
      console.error('Ошибка при загрузке ролей:', err)
      setError('Не удалось загрузить роли')
    }
  }

  /**
   * Загрузка списка публикаций с учетом пагинации и поиска
   */
  async function loadShouts() {
    setShowRolesModal(false)
    setShoutsLoading(true)
    const pagination = shoutsPagination()

    try {
      const result = await query<AdminGetShoutsData>(
        `${location.origin}/graphql`,
        ADMIN_GET_SHOUTS_QUERY,
        {
          offset: (pagination.page - 1) * pagination.limit,
          limit: pagination.limit,
          status: shoutsStatus()
        }
      )

      if (result?.adminGetShouts) {
        setShouts(result.adminGetShouts.shouts)
        // Обновляем пагинацию с учетом общего количества
        setShoutsPagination({
          ...pagination,
          total: result.adminGetShouts.total,
          totalPages: result.adminGetShouts.totalPages
        })
      }
    } catch (error) {
      console.error('Error loading shouts:', error)
    } finally {
      setShoutsLoading(false)
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
      await query<AdminUpdateUserResponse>(
        `${location.origin}/graphql`,
        `
        mutation AdminUpdateUser($user: AdminUserUpdateInput!) {
          adminUpdateUser(user: $user) {
            success
            error
          }
        }
      `,
        {
          user: {
            id: userId,
            roles: newRoles,
            community: 1 // Добавляем обязательный параметр community
          }
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

      // Показываем сообщение об успехе и обновляем список пользователей
      setSuccessMessage('Роли пользователя успешно обновлены')

      // Перезагружаем список пользователей
      loadUsers()

      // Скрываем сообщение через 3 секунды
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      console.error('Ошибка обновления ролей:', err)
      let errorMessage = err instanceof Error ? err.message : 'Ошибка обновления ролей';

      // Если ошибка связана с недостающим полем community
      if (errorMessage.includes('author_role.community')) {
        errorMessage = 'Ошибка: для роли author требуется указать community. Обратитесь к администратору.';
      }

      setError(errorMessage)
    }
  }

  /**
   * Обрабатывает выход из системы
   */
  const handleLogout = async () => {
    try {
      await logout()
      if (props.onLogout) {
        props.onLogout()
      }
    } catch (error) {
      setError('Ошибка при выходе: ' + (error as Error).message)
    }
  }

  /**
   * Форматирование даты в формате "X дней назад"
   * @param timestamp - Временная метка
   * @returns Форматированная строка с относительной датой
   */
  function formatDateRelative(timestamp?: number): string {
    if (!timestamp) return 'Н/Д'

    const now = Math.floor(Date.now() / 1000)
    const diff = now - timestamp

    // Меньше минуты
    if (diff < 60) {
      return 'только что'
    }

    // Меньше часа
    if (diff < 3600) {
      const minutes = Math.floor(diff / 60)
      return `${minutes} ${getMinutesForm(minutes)} назад`
    }

    // Меньше суток
    if (diff < 86400) {
      const hours = Math.floor(diff / 3600)
      return `${hours} ${getHoursForm(hours)} назад`
    }

    // Меньше 30 дней
    if (diff < 2592000) {
      const days = Math.floor(diff / 86400)
      return `${days} ${getDaysForm(days)} назад`
    }

    // Меньше года
    if (diff < 31536000) {
      const months = Math.floor(diff / 2592000)
      return `${months} ${getMonthsForm(months)} назад`
    }

    // Больше года
    const years = Math.floor(diff / 31536000)
    return `${years} ${getYearsForm(years)} назад`
  }

  /**
   * Получение правильной формы слова "минута" в зависимости от числа
   * @param minutes - Количество минут
   */
  function getMinutesForm(minutes: number): string {
    if (minutes % 10 === 1 && minutes % 100 !== 11) {
      return 'минуту'
    } else if ([2, 3, 4].includes(minutes % 10) && ![12, 13, 14].includes(minutes % 100)) {
      return 'минуты'
    }
    return 'минут'
  }

  /**
   * Получение правильной формы слова "час" в зависимости от числа
   * @param hours - Количество часов
   */
  function getHoursForm(hours: number): string {
    if (hours % 10 === 1 && hours % 100 !== 11) {
      return 'час'
    } else if ([2, 3, 4].includes(hours % 10) && ![12, 13, 14].includes(hours % 100)) {
      return 'часа'
    }
    return 'часов'
  }

  /**
   * Получение правильной формы слова "день" в зависимости от числа
   * @param days - Количество дней
   */
  function getDaysForm(days: number): string {
    if (days % 10 === 1 && days % 100 !== 11) {
      return 'день'
    } else if ([2, 3, 4].includes(days % 10) && ![12, 13, 14].includes(days % 100)) {
      return 'дня'
    }
    return 'дней'
  }

  /**
   * Получение правильной формы слова "месяц" в зависимости от числа
   * @param months - Количество месяцев
   */
  function getMonthsForm(months: number): string {
    if (months % 10 === 1 && months % 100 !== 11) {
      return 'месяц'
    } else if ([2, 3, 4].includes(months % 10) && ![12, 13, 14].includes(months % 100)) {
      return 'месяца'
    }
    return 'месяцев'
  }

  /**
   * Получение правильной формы слова "год" в зависимости от числа
   * @param years - Количество лет
   */
  function getYearsForm(years: number): string {
    if (years % 10 === 1 && years % 100 !== 11) {
      return 'год'
    } else if ([2, 3, 4].includes(years % 10) && ![12, 13, 14].includes(years % 100)) {
      return 'года'
    }
    return 'лет'
  }

  /**
   * Получает иконку для роли пользователя
   * @param role - Название роли
   * @returns Иконка для роли
   */
  function getRoleIcon(role: string): string {
    switch (role.toLowerCase()) {
      case 'admin':
        return '👑' // корона для администратора
      case 'moderator':
        return '🛡️' // щит для модератора
      case 'editor':
        return '✏️' // карандаш для редактора
      case 'author':
        return '📝' // блокнот для автора
      case 'user':
        return '👤' // фигура для обычного пользователя
      case 'subscriber':
        return '📬' // почтовый ящик для подписчика
      case 'guest':
        return '👋' // рука для гостя
      case 'banned':
        return '🚫' // знак запрета для заблокированного
      case 'vip':
        return '⭐' // звезда для VIP
      case 'verified':
        return '✓' // галочка для верифицированного
      default:
        return '🔹' // точка для прочих ролей
    }
  }

  /**
   * Компонент для отображения роли с иконкой
   */
  const RoleBadge: Component<{ role: string }> = (props) => {
    return (
      <span class="role-badge" title={props.role}>
        <span class="role-icon">{getRoleIcon(props.role)}</span>
        <span class="role-name">{props.role}</span>
      </span>
    )
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
    const availableRoles = roles(); // Получаем список доступных ролей

    // Получаем дополнительные описания ролей
    const getRoleDescription = (roleId: string): string => {
      // Иначе возвращаем стандартное описание
      switch(roleId) {
        case 'reader':
          return 'Базовая роль. Позволяет авторизоваться и оставлять реакции.';
        case 'expert':
          return 'Эксперт. Позволяет оставлять комментарии и апрувить публикации для главной.';
        case 'author':
          return 'Расширенная роль. Позволяет создавать контент и голосовать за публикации для вывода на главную страницу.';
        case 'editor':
          return 'Редактор. Позволяет редактировать темы и публикации сообщества.';
        case 'moderator':
          return 'Модератор. Позволяет модерировать контент и управлять пользователями.';
        case 'admin':
          return 'Администратор. Позволяет управлять всеми функциями системы.';
        default:
          return 'Нет описания';
      }
    };

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
        // При сохранении ролей передаем правильный набор параметров
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
            <For each={availableRoles}>
              {(role) => (
                <div class="role-item">
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedRoles().includes(role.id)}
                      onChange={() => toggleRole(role.id)}
                    />
                    {role.id}
                  </label>
                  <p class="role-description">{getRoleDescription(role.id)}</p>
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

  /**
   * Загружает переменные окружения
   */
  const loadEnvVariables = async () => {
    try {
      setEnvLoading(true)
      setError(null)

      const result = await query(props.apiUrl, `
        query GetEnvVariables {
          getEnvVariables {
            name
            description
            variables {
              key
              value
              description
              type
              isSecret
            }
          }
        }
      `)

      if (result.getEnvVariables) {
        setEnvSections(result.getEnvVariables as EnvSection[])
      }
    } catch (err) {
      console.error('Ошибка загрузки переменных окружения:', err)
      setError('Не удалось загрузить переменные окружения: ' + (err as Error).message)

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
      setEnvLoading(false)
    }
  }

  /**
   * Обновляет значение переменной окружения
   */
  const updateEnvVariable = async (key: string, value: string) => {
    try {
      setError(null)
      setSuccessMessage(null)

      const result = await query(props.apiUrl, `
        mutation UpdateEnvVariable($key: String!, $value: String!) {
          updateEnvVariable(key: $key, value: $value)
        }
      `, { key, value })

      if (result.updateEnvVariable) {
        setSuccessMessage(`Переменная ${key} успешно обновлена`)
        // Обновляем список переменных
        await loadEnvVariables()
      } else {
        setError('Не удалось обновить переменную')
      }
    } catch (err) {
      console.error('Ошибка обновления переменной:', err)
      setError('Ошибка при обновлении переменной: ' + (err as Error).message)

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
   * Обработчик открытия модального окна редактирования переменной
   */
  const openVariableModal = (variable: EnvVariable) => {
    setEditingVariable({ ...variable })
    setShowVariableModal(true)
  }

  /**
   * Обработчик закрытия модального окна редактирования переменной
   */
  const closeVariableModal = () => {
    setEditingVariable(null)
    setShowVariableModal(false)
  }

  /**
   * Обработчик сохранения переменной
   */
  const saveVariable = async () => {
    const variable = editingVariable()
    if (!variable) return

    await updateEnvVariable(variable.key, variable.value)
    closeVariableModal()
  }

  /**
   * Обработчик изменения значения в модальном окне
   */
  const handleVariableValueChange = (value: string) => {
    const variable = editingVariable()
    if (variable) {
      setEditingVariable({ ...variable, value })
    }
  }

  /**
   * Загружает список переменных среды при переключении на соответствующую вкладку
   */
  const handleTabChange = (tab: string) => {
    setActiveTab(tab)
    setError(null)
    setSuccessMessage(null)

    if (tab === 'env' && envSections().length === 0) {
      loadEnvVariables()
    } else if (tab === 'shouts' && shouts().length === 0) {
      loadShouts()
    }
  }

  /**
   * Кнопка копирования значения переменной окружения
   * @param value - значение для копирования
   */
  function CopyButton({ value }: { value: string }) {
    /**
     * Копирует значение в буфер обмена
     * @param e - событие клика
     */
    const handleCopy = async (e: MouseEvent) => {
      e.preventDefault()
      try {
        await navigator.clipboard.writeText(value)
        // Можно добавить всплывающее уведомление
      } catch (err) {
        alert('Ошибка копирования: ' + (err as Error).message)
      }
    }
    return (
      <a class="btn" title="Скопировать" type="button" style="margin-left: 6px" onClick={handleCopy}>
        📋
      </a>
    )
  }

  /**
   * Кнопка показать/скрыть значение переменной
   * @param shown - показывать ли значение
   * @param onToggle - обработчик переключения
   */
  function ShowHideButton({ shown, onToggle }: { shown: boolean, onToggle: () => void }) {
    return (
      <a class="btn" title={shown ? 'Скрыть' : 'Показать'} type="button" style="margin-left: 6px" onClick={onToggle}>
        {shown ? '🙈' : '👁️'}
      </a>
    )
  }

  /**
   * Компонент модального окна для редактирования переменной окружения
   */
  const VariableModal: Component = () => {
    const variable = editingVariable()

    if (!variable) return null

    return (
      <div class="modal-overlay">
        <div class="modal-content">
          <h2>Редактирование переменной</h2>
          <p>Переменная: {variable.key}</p>

          <div class="variable-edit-form">
            <div class="form-group">
              <label>Значение:</label>
              <input
                type={variable.isSecret ? 'password' : 'text'}
                value={variable.value}
                onInput={(e) => handleVariableValueChange(e.target.value)}
              />
            </div>

            <Show when={variable.description}>
              <div class="variable-description">
                <p>{variable.description}</p>
              </div>
            </Show>
          </div>

          <div class="modal-actions">
            <button class="cancel-button" onClick={closeVariableModal}>
              Отмена
            </button>
            <button class="save-button" onClick={saveVariable}>
              Сохранить
            </button>
          </div>
        </div>
      </div>
    )
  }

  /**
   * Компонент для отображения переменных окружения
   */
  const EnvVariablesTab: Component = () => {
    // Сигналы для показа/скрытия значений по ключу
    const [shownVars, setShownVars] = createSignal<{ [key: string]: boolean }>({})

    /**
     * Переключает показ значения переменной
     * @param key - ключ переменной
     */
    const toggleShow = (key: string) => {
      setShownVars((prev) => ({ ...prev, [key]: !prev[key] }))
    }

    return (
      <div class="env-variables-container">
        <Show when={envLoading()}>
          <div class="loading">Загрузка переменных окружения...</div>
        </Show>

        <Show when={!envLoading() && envSections().length === 0}>
          <div class="empty-state">Нет доступных переменных окружения</div>
        </Show>

        <Show when={!envLoading() && envSections().length > 0}>
          <div class="env-sections">
            <For each={envSections()}>
              {(section) => (
                <div class="env-section">
                  <h3 class="section-name">{section.name}</h3>
                  <Show when={section.description}>
                    <p class="section-description">{section.description}</p>
                  </Show>
                  <div class="variables-list">
                    <table>
                      <thead>
                        <tr>
                          <th>Ключ</th>
                          <th>Значение</th>
                          <th>Описание</th>
                          <th>Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        <For each={section.variables}>
                          {(variable) => {
                            const shown = () => shownVars()[variable.key] || false
                            return (
                              <tr>
                                <td>{variable.key}</td>
                                <td>
                                  {variable.isSecret && !shown()
                                    ? '••••••••'
                                    : (variable.value || <span class="empty-value">не задано</span>)}
                                  <CopyButton value={variable.value || ''} />
                                  {variable.isSecret && (
                                    <ShowHideButton shown={shown()} onToggle={() => toggleShow(variable.key)} />
                                  )}
                                </td>
                                <td>{variable.description || '-'}</td>
                                <td class="actions">
                                  <button
                                    class="edit-button"
                                    onClick={() => openVariableModal(variable)}
                                  >
                                    Изменить
                                  </button>
                                </td>
                              </tr>
                            )
                          }}
                        </For>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </For>
          </div>
        </Show>
      </div>
    )
  }

  // Вспомогательные функции для публикаций
  function getShoutStatus(shout: Shout): string {
    if (shout.deleted_at) return 'Удалена'
    if (shout.published_at) return 'Опубликована'
    return 'Черновик'
  }

  function getShoutStatusClass(shout: Shout): string {
    if (shout.deleted_at) return 'status-deleted'
    if (shout.published_at) return 'status-published'
    return 'status-draft'
  }

  function truncateText(text: string, maxLength: number = 100): string {
    if (!text || text.length <= maxLength) return text
    return text.substring(0, maxLength) + '...'
  }

  /**
   * Определяет язык контента (html или json)
   */
  function detectLanguage(content: string): string {
    // Пробуем распарсить как JSON
    try {
      JSON.parse(content)
      return 'json'
    } catch {
      // Проверяем на наличие HTML тегов
      if (/<[^>]*>/g.test(content)) {
        return 'markup'
      }
    }
    return 'plaintext'
  }

  /**
   * Форматирует XML/HTML с отступами
   */
  function prettyFormatXML(xml: string): string {
    let formatted = '';
    const reg = /(>)(<)(\/*)/g;
    xml = xml.replace(reg, '$1\r\n$2$3');
    let pad = 0;
    xml.split('\r\n').forEach((node) => {
      let indent = 0;
      if (node.match(/.+<\/\w[^>]*>$/)) {
        indent = 0;
      } else if (node.match(/^<\//)) {
        if (pad !== 0) pad -= 2;
      } else if (node.match(/^<\w([^>]*[^/])?>.*$/)) {
        indent = 2;
      } else {
        indent = 0;
      }
      formatted += ' '.repeat(pad) + node + '\r\n';
      pad += indent;
    });
    return formatted.trim();
  }

  /**
   * Форматирует и подсвечивает код
   */
  function formatCode(content: string): string {
    const language = detectLanguage(content)

    if (language === 'json') {
      try {
        // Форматируем JSON с отступами
        const formatted = JSON.stringify(JSON.parse(content), null, 2)
        return Prism.highlight(formatted, Prism.languages[language], language)
      } catch {
        return content
      }
    } else if (language === 'markup') {
      // Форматируем XML/HTML с отступами
      const formatted = prettyFormatXML(content)
      return Prism.highlight(formatted, Prism.languages[language], language)
    }

    return content
  }

  /**
   * Компонент модального окна для просмотра содержимого публикации
   */
  const BodyModal: Component = () => {
    const language = () => detectLanguage(selectedShoutBody())
    const formattedCode = () => formatCode(selectedShoutBody())

    return (
      <Show when={showBodyModal()}>
        <div class="modal-overlay" onClick={() => setShowBodyModal(false)}>
          <div class="modal-content" onClick={(e) => e.stopPropagation()}>
            <div class="modal-body">
              <pre class="body-content">
                <code class={`language-${language()}`} innerHTML={formattedCode()} />
              </pre>
            </div>
          </div>
        </div>
      </Show>
    )
  }

  /**
   * Компонент модального окна для просмотра содержимого media.body
   */
  const MediaBodyModal: Component = () => {
    const language = () => detectLanguage(selectedMediaBody())
    const formattedCode = () => formatCode(selectedMediaBody())

    return (
      <Show when={showMediaBodyModal()}>
        <div class="modal-overlay" onClick={() => setShowMediaBodyModal(false)}>
          <div class="modal-content" onClick={(e) => e.stopPropagation()}>
            <div class="modal-header">
              <div class="modal-title">
                <h3>Содержимое media.body</h3>
                <span class="language-badge">
                  {language() === 'markup' ? 'HTML' :
                   language() === 'json' ? 'JSON' :
                   'Plain Text'}
                </span>
              </div>
              <button class="close-button" onClick={() => setShowMediaBodyModal(false)}>×</button>
            </div>
            <div class="modal-body">
              <pre class="body-content">
                <code class={`language-${language()}`} innerHTML={formattedCode()} />
              </pre>
            </div>
          </div>
        </div>
      </Show>
    )
  }

  /**
   * Обработчик изменения страницы для публикаций
   * @param page - Номер страницы
   */
  function handleShoutsPageChange(page: number) {
    setShoutsPagination({ ...shoutsPagination(), page })
    loadShouts()
  }

  /**
   * Обработчик изменения количества публикаций на странице
   * @param limit - Количество элементов
   */
  function handleShoutsPerPageChange(limit: number) {
    setShoutsPagination({ ...shoutsPagination(), page: 1, limit })
    loadShouts()
  }

  /**
   * Компонент пагинации для публикаций
   */
  const ShoutsPagination: Component = () => {
    const pagination = shoutsPagination()
    const totalPages = pagination.totalPages
    const currentPage = pagination.page

    // Генерируем массив страниц для отображения
    const pages = []
    const maxVisiblePages = 5 // Максимальное количество видимых страниц

    // Всегда показываем первую страницу
    pages.push(1)

    // Вычисляем диапазон страниц вокруг текущей
    let startPage = Math.max(2, currentPage - Math.floor(maxVisiblePages / 2))
    let endPage = Math.min(totalPages - 1, startPage + maxVisiblePages - 2)

    // Корректируем диапазон, если он выходит за границы
    if (endPage - startPage < maxVisiblePages - 2) {
      startPage = Math.max(2, endPage - maxVisiblePages + 2)
    }

    // Добавляем многоточие после первой страницы, если нужно
    if (startPage > 2) {
      pages.push('...')
    }

    // Добавляем страницы из диапазона
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i)
    }

    // Добавляем многоточие перед последней страницей, если нужно
    if (endPage < totalPages - 1) {
      pages.push('...')
    }

    // Всегда показываем последнюю страницу, если есть больше одной страницы
    if (totalPages > 1) {
      pages.push(totalPages)
    }

    return (
      <div class="pagination">
        <div class="pagination-info">
          Показано {((currentPage - 1) * pagination.limit) + 1} - {Math.min(currentPage * pagination.limit, pagination.total)} из {pagination.total}
        </div>

        <div class="pagination-controls">
          <button
            class="pagination-button"
            onClick={() => handleShoutsPageChange(currentPage - 1)}
            disabled={currentPage === 1}
          >
            ←
          </button>

          <For each={pages}>
            {(page) => (
              <>
                {page === '...' ? (
                  <span class="pagination-ellipsis">...</span>
                ) : (
                  <button
                    class={`pagination-button ${page === currentPage ? 'active' : ''}`}
                    onClick={() => handleShoutsPageChange(Number(page))}
                  >
                    {page}
                  </button>
                )}
              </>
            )}
          </For>

          <button
            class="pagination-button"
            onClick={() => handleShoutsPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            →
          </button>
        </div>

        <div class="pagination-per-page">
          На странице:
          <select
            value={pagination.limit}
            onChange={(e) => handleShoutsPerPageChange(Number(e.target.value))}
          >
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
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
          <button class={activeTab() === 'users' ? 'active' : ''} onClick={() => handleTabChange('users')}>
            Пользователи
          </button>
          <button class={activeTab() === 'shouts' ? 'active' : ''} onClick={() => handleTabChange('shouts')}>
            Публикации
          </button>
          <button class={activeTab() === 'env' ? 'active' : ''} onClick={() => handleTabChange('env')}>
            Переменные среды
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

        <Show when={activeTab() === 'users'}>
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
                    <th>Создан</th>
                    <th>Роли</th>
                  </tr>
                </thead>
                <tbody>
                  <For each={users()}>
                    {(user) => (
                      <tr>
                        <td>{user.id}</td>
                        <td>{user.email}</td>
                        <td>{user.name || '-'}</td>
                        <td>{formatDateRelative(user.created_at)}</td>
                        <td class="roles-cell">
                          <div class="roles-container">
                            <For each={user.roles}>
                              {(role) => <RoleBadge role={role} />}
                            </For>
                            <div class="role-badge edit-role-badge" onClick={() => {
                                  setSelectedUser(user)
                                  setShowRolesModal(true)
                                }}
                              >
                                <span class="role-icon">🎭</span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </For>
                </tbody>
              </table>
            </div>

            <Pagination />
          </Show>
        </Show>

        <Show when={activeTab() === 'shouts'}>
          <Show when={shoutsLoading()}>
            <div class="loading">Загрузка публикаций...</div>
          </Show>

          <Show when={!shoutsLoading() && shouts().length === 0 && !error()}>
            <div class="empty-state">Нет публикаций для отображения</div>
          </Show>

          <Show when={!shoutsLoading() && shouts().length > 0}>
            <div class="shouts-controls">
              <div class="search-container">
                <div class="search-input-group">
                  <input
                    type="text"
                    placeholder="Поиск по заголовку, slug или ID..."
                    value={shoutsSearchQuery()}
                    onInput={(e) => setShoutsSearchQuery(e.currentTarget.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        loadShouts()
                      }
                    }}
                    class="search-input"
                  />
                  <button class="search-button" onClick={loadShouts}>
                    Поиск
                  </button>
                </div>
              </div>

              <div class="status-filter">
                <select
                  value={shoutsStatus()}
                  onInput={(e) => {
                    setShoutsStatus(e.currentTarget.value)
                    loadShouts()
                  }}
                >
                  <option value="all">Все</option>
                  <option value="published">Опубликованные</option>
                  <option value="draft">Черновики</option>
                  <option value="deleted">Удаленные</option>
                </select>
              </div>
            </div>

            <div class="shouts-list">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Заголовок</th>
                    <th>Slug</th>
                    <th>Статус</th>
                    <th>Авторы</th>
                    <th>Темы</th>
                    <th>Создан</th>
                    <th>Содержимое</th>
                    <th>Media</th>
                  </tr>
                </thead>
                <tbody>
                  <For each={shouts()}>
                    {(shout) => (
                      <tr>
                        <td>{shout.id}</td>
                        <td title={shout.title}>{truncateText(shout.title, 50)}</td>
                        <td title={shout.slug}>{truncateText(shout.slug, 30)}</td>
                        <td>
                          <span class={`status-badge ${getShoutStatusClass(shout)}`}>
                            {getShoutStatus(shout)}
                          </span>
                        </td>
                        <td>
                          <Show when={shout.authors && shout.authors.length > 0}>
                            <div class="authors-list">
                              <For each={shout.authors}>
                                {(author) => (
                                  <span class="author-badge" title={author.email}>
                                    {author.name || author.email || `ID:${author.id}`}
                                  </span>
                                )}
                              </For>
                            </div>
                          </Show>
                          <Show when={!shout.authors || shout.authors.length === 0}>
                            <span class="no-data">-</span>
                          </Show>
                        </td>
                        <td>
                          <Show when={shout.topics && shout.topics.length > 0}>
                            <div class="topics-list">
                              <For each={shout.topics}>
                                {(topic) => (
                                  <span class="topic-badge" title={topic.slug}>
                                    {topic.title || topic.slug}
                                  </span>
                                )}
                              </For>
                            </div>
                          </Show>
                          <Show when={!shout.topics || shout.topics.length === 0}>
                            <span class="no-data">-</span>
                          </Show>
                        </td>
                        <td>{formatDateRelative(shout.created_at)}</td>
                        <td
                          class="body-cell"
                          onClick={() => {
                            setSelectedShoutBody(shout.body)
                            setShowBodyModal(true)
                          }}
                          style="cursor: pointer; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                        >
                          {truncateText(shout.body.replace(/<[^>]*>/g, ''), 100)}
                        </td>
                        <td>
                          <Show when={shout.media && shout.media.length > 0}>
                            <div style="display: flex; flex-direction: column; gap: 4px;">
                              <For each={shout.media}>
                                {(mediaItem, idx) => (
                                  <div style="display: flex; align-items: center; gap: 6px;">
                                    <span class="media-count">{mediaItem.title || `media[${idx()}]`}</span>
                                    <Show when={mediaItem.body}>
                                      <button
                                        class="edit-button"
                                        style="padding: 2px 8px; font-size: 12px;"
                                        title="Показать содержимое body"
                                        onClick={() => {
                                          setSelectedMediaBody(mediaItem.body)
                                          setShowMediaBodyModal(true)
                                        }}
                                      >👁 body</button>
                                    </Show>
                                  </div>
                                )}
                              </For>
                            </div>
                          </Show>
                          <Show when={!shout.media || shout.media.length === 0}>
                            <span class="no-data">-</span>
                          </Show>
                        </td>
                      </tr>
                    )}
                  </For>
                </tbody>
              </table>
              <ShoutsPagination />
            </div>
          </Show>
        </Show>

        <Show when={activeTab() === 'env'}>
          <EnvVariablesTab />
        </Show>
      </main>

      <Show when={showRolesModal()}>
        <RolesModal />
      </Show>

      <Show when={showVariableModal()}>
        <VariableModal />
      </Show>

      <BodyModal />
      <MediaBodyModal />
    </div>
  )
}

export default AdminPage
