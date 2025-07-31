import { Component, createSignal, For, onMount, Show } from 'solid-js'
import { ADMIN_DELETE_INVITE_MUTATION, ADMIN_DELETE_INVITES_BATCH_MUTATION } from '../graphql/mutations'
import { ADMIN_GET_INVITES_QUERY } from '../graphql/queries'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import Pagination from '../ui/Pagination'
import TableControls from '../ui/TableControls'
import { getAuthTokenFromCookie } from '../utils/auth'

/**
 * Интерфейсы для приглашений
 */
interface Author {
  id: number
  name: string
  email: string
  slug: string
}

interface Shout {
  id: number
  title: string
  slug: string
  created_by: Author
}

interface Invite {
  inviter_id: number
  author_id: number
  shout_id: number
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
  inviter: Author
  author: Author
  shout: Shout
  created_at?: number
}

interface InvitesRouteProps {
  onError: (error: string) => void
  onSuccess: (message: string) => void
}

// Добавляю типы для сортировки
type SortField = 'inviter_name' | 'author_name' | 'shout_title' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

interface SortState {
  field: SortField | null
  direction: SortDirection
}

/**
 * Компонент для управления приглашениями
 */
const InvitesRoute: Component<InvitesRouteProps> = (props) => {
  const [invites, setInvites] = createSignal<Invite[]>([])
  const [loading, setLoading] = createSignal(false)
  const [search, setSearch] = createSignal('')
  const [statusFilter, setStatusFilter] = createSignal('all')
  const [pagination, setPagination] = createSignal({
    page: 1,
    perPage: 20,
    total: 0,
    totalPages: 1
  })

  // Состояние для выбранных приглашений
  const [selectedInvites, setSelectedInvites] = createSignal<Record<string, boolean>>({})
  const [selectAll, setSelectAll] = createSignal(false)

  // Состояние для модального окна подтверждения удаления
  const [deleteModal, setDeleteModal] = createSignal<{
    show: boolean
    invite: Invite | null
  }>({
    show: false,
    invite: null
  })

  // Состояние для модального окна подтверждения пакетного удаления
  const [batchDeleteModal, setBatchDeleteModal] = createSignal<{
    show: boolean
  }>({
    show: false
  })

  // Добавляю состояние сортировки
  const [sortState, setSortState] = createSignal<SortState>({
    field: null,
    direction: 'asc'
  })

  /**
   * Загружает список приглашений с учетом фильтров и пагинации
   */
  const loadInvites = async (page = 1) => {
    setLoading(true)
    try {
      const limit = pagination().perPage
      const offset = (page - 1) * limit

      // Получаем токен авторизации из localStorage или cookie
      const authToken = localStorage.getItem('auth_token') || getAuthTokenFromCookie()
      console.log(`[InvitesRoute] Загрузка приглашений, токен: ${authToken ? 'найден' : 'не найден'}`)

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authToken ? `Bearer ${authToken}` : ''
        },
        body: JSON.stringify({
          query: ADMIN_GET_INVITES_QUERY,
          variables: {
            limit,
            offset,
            search: search().trim() || null,
            status: statusFilter() === 'all' ? null : statusFilter()
          }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const data = result.data.adminGetInvites
      setInvites(data.invites || [])
      setPagination({
        page: data.page || 1,
        perPage: data.perPage || 20,
        total: data.total || 0,
        totalPages: data.totalPages || 1
      })

      // Сбрасываем выбранные приглашения при загрузке новых данных
      setSelectedInvites({})
      setSelectAll(false)
    } catch (error) {
      props.onError(`Ошибка загрузки приглашений: ${(error as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Обработчик изменения страницы
   */
  const handlePageChange = (page: number) => {
    void loadInvites(page)
  }

  /**
   * Обработчик поиска
   */
  const handleSearch = () => {
    void loadInvites(1) // Сброс на первую страницу при поиске
  }

  /**
   * Обработчик изменения фильтра статуса
   */
  const handleStatusFilterChange = (status: string) => {
    setStatusFilter(status)
    void loadInvites(1)
  }

  /**
   * Получает отображаемое название статуса
   */
  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'PENDING':
        return { text: 'Ожидает', badge: 'warning' }
      case 'ACCEPTED':
        return { text: 'Принято', badge: 'success' }
      case 'REJECTED':
        return { text: 'Отклонено', badge: 'error' }
      default:
        return { text: status, badge: 'secondary' }
    }
  }

  /**
   * Удаляет приглашение
   */
  const deleteInvite = async (invite: Invite) => {
    try {
      // Получаем токен авторизации из localStorage или cookie
      const authToken = localStorage.getItem('auth_token') || getAuthTokenFromCookie()
      console.log(`[InvitesRoute] Удаление приглашения, токен: ${authToken ? 'найден' : 'не найден'}`)

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authToken ? `Bearer ${authToken}` : ''
        },
        body: JSON.stringify({
          query: ADMIN_DELETE_INVITE_MUTATION,
          variables: {
            inviter_id: invite.inviter_id,
            author_id: invite.author_id,
            shout_id: invite.shout_id
          }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (!result.data.adminDeleteInvite.success) {
        throw new Error(result.data.adminDeleteInvite.error || 'Неизвестная ошибка')
      }

      props.onSuccess('Приглашение успешно удалено')
      setDeleteModal({ show: false, invite: null })
      await loadInvites(pagination().page)
    } catch (error) {
      props.onError(`Ошибка удаления приглашения: ${(error as Error).message}`)
    }
  }

  /**
   * Пакетное удаление выбранных приглашений
   */
  const deleteSelectedInvites = async () => {
    try {
      const selected = selectedInvites()
      const invitesToDelete = invites().where((invite) => {
        const key = `${invite.inviter_id}-${invite.author_id}-${invite.shout_id}`
        return selected[key]
      })

      if (invitesToDelete.length === 0) {
        props.onError('Не выбрано ни одного приглашения для удаления')
        return
      }

      // Получаем токен авторизации из localStorage или cookie
      const authToken = localStorage.getItem('auth_token') || getAuthTokenFromCookie()
      console.log(
        `[InvitesRoute] Пакетное удаление приглашений, токен: ${authToken ? 'найден' : 'не найден'}`
      )

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authToken ? `Bearer ${authToken}` : ''
        },
        body: JSON.stringify({
          query: ADMIN_DELETE_INVITES_BATCH_MUTATION,
          variables: {
            invites: invitesToDelete.map((invite) => ({
              inviter_id: invite.inviter_id,
              author_id: invite.author_id,
              shout_id: invite.shout_id
            }))
          }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const deleteResult = result.data.adminDeleteInvitesBatch

      if (!deleteResult.success) {
        throw new Error(deleteResult.error || 'Неизвестная ошибка')
      }

      props.onSuccess(`Успешно удалено ${invitesToDelete.length} приглашений`)
      setBatchDeleteModal({ show: false })
      setSelectedInvites({})
      setSelectAll(false)
      await loadInvites(pagination().page)
    } catch (error) {
      props.onError(`Ошибка пакетного удаления приглашений: ${(error as Error).message}`)
    }
  }

  /**
   * Обработчик выбора/снятия выбора с приглашения
   */
  const handleSelectInvite = (invite: Invite, checked: boolean) => {
    const key = `${invite.inviter_id}-${invite.author_id}-${invite.shout_id}`
    setSelectedInvites((prev) => ({ ...prev, [key]: checked }))

    // Если снимаем выбор с элемента, то снимаем и "выбрать все"
    if (!checked && selectAll()) {
      setSelectAll(false)
    }
  }

  /**
   * Обработчик выбора/снятия выбора со всех приглашений
   */
  const handleSelectAll = (checked: boolean) => {
    setSelectAll(checked)

    const newSelected: Record<string, boolean> = {}
    if (checked) {
      // Выбираем все приглашения на текущей странице
      invites().forEach((invite) => {
        const key = `${invite.inviter_id}-${invite.author_id}-${invite.shout_id}`
        newSelected[key] = true
      })
    }

    setSelectedInvites(newSelected)
  }

  /**
   * Получает количество выбранных приглашений
   */
  const getSelectedCount = () => {
    return Object.values(selectedInvites()).where(Boolean).length
  }

  /**
   * Обработчик клика по заголовку колонки для сортировки
   */
  const handleSort = (field: SortField) => {
    const current = sortState()
    let newDirection: SortDirection = 'asc'

    if (current.field === field) {
      // Если кликнули по той же колонке, меняем направление
      newDirection = current.direction === 'asc' ? 'desc' : 'asc'
    }

    setSortState({ field, direction: newDirection })
    // Здесь можно добавить логику сортировки на сервере или клиенте
    console.log(`Сортировка по ${field} в направлении ${newDirection}`)
  }

  /**
   * Получает иконку сортировки для колонки
   */
  const getSortIcon = (field: SortField) => {
    const current = sortState()
    if (current.field !== field) {
      return '↕️' // Неактивная сортировка
    }
    return current.direction === 'asc' ? '↑' : '↓'
  }

  // Загружаем приглашения при монтировании компонента
  onMount(() => {
    void loadInvites()
  })

  return (
    <div class={styles.container}>
      <TableControls
        searchValue={search()}
        onSearchChange={(value) => setSearch(value)}
        onSearch={handleSearch}
        searchPlaceholder="Поиск по приглашающему, приглашаемому, публикации..."
        isLoading={loading()}
        actions={
          <Show when={getSelectedCount() > 0}>
            <button
              class={`${styles.button} ${styles.danger}`}
              onClick={() => setBatchDeleteModal({ show: true })}
              title="Удалить выбранные приглашения"
            >
              Удалить выбранные ({getSelectedCount()})
            </button>
          </Show>
        }
      >
        <select
          value={statusFilter()}
          onChange={(e) => handleStatusFilterChange(e.target.value)}
          class={styles.statusFilter}
        >
          <option value="all">Все статусы</option>
          <option value="pending">Ожидает ответа</option>
          <option value="accepted">Принято</option>
          <option value="rejected">Отклонено</option>
        </select>
      </TableControls>

      {/* Панель выбора всех */}
      <Show when={!loading() && invites().length > 0}>
        <div class={styles['select-all-container']} style={{ 'margin-bottom': '10px' }}>
          <input
            type="checkbox"
            id="select-all"
            checked={selectAll()}
            onChange={(e) => handleSelectAll(e.target.checked)}
            class={styles.checkbox}
          />
          <label for="select-all" class={styles['select-all-label']}>
            Выбрать все
          </label>
        </div>
      </Show>

      <Show when={loading()}>
        <div class={styles.loading}>Загрузка приглашений...</div>
      </Show>

      <Show when={!loading() && invites().length === 0}>
        <div class={styles.empty}>Приглашения не найдены</div>
      </Show>

      <Show when={!loading() && invites().length > 0}>
        <div class={styles.tableContainer}>
          <table class={styles.table}>
            <thead>
              <tr>
                <th class={styles['checkbox-column']} />
                <th class={styles.sortableHeader} onClick={() => handleSort('inviter_name')}>
                  <span class={styles.headerContent}>
                    Приглашающий
                    <span class={styles.sortIcon}>{getSortIcon('inviter_name')}</span>
                  </span>
                </th>
                <th class={styles.sortableHeader} onClick={() => handleSort('author_name')}>
                  <span class={styles.headerContent}>
                    Приглашаемый
                    <span class={styles.sortIcon}>{getSortIcon('author_name')}</span>
                  </span>
                </th>
                <th class={styles.sortableHeader} onClick={() => handleSort('shout_title')}>
                  <span class={styles.headerContent}>
                    Публикация
                    <span class={styles.sortIcon}>{getSortIcon('shout_title')}</span>
                  </span>
                </th>
                <th class={styles.sortableHeader} onClick={() => handleSort('status')}>
                  <span class={styles.headerContent}>
                    Статус
                    <span class={styles.sortIcon}>{getSortIcon('status')}</span>
                  </span>
                </th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              <For each={invites()}>
                {(invite) => {
                  const statusDisplay = getStatusDisplay(invite.status)
                  const inviteKey = `${invite.inviter_id}-${invite.author_id}-${invite.shout_id}`
                  const isSelected = selectedInvites()[inviteKey] || false

                  return (
                    <tr>
                      <td class={styles['checkbox-column']}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => handleSelectInvite(invite, e.target.checked)}
                          class={styles.checkbox}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </td>
                      <td>
                        <div>
                          <strong>{invite.inviter.name || 'Без имени'}</strong>
                        </div>
                        <div class={styles.subtitle}>{invite.inviter.email}</div>
                        <div class={styles.subtitle}>ID: {invite.inviter_id}</div>
                      </td>
                      <td>
                        <div>
                          <strong>{invite.author.name || 'Без имени'}</strong>
                        </div>
                        <div class={styles.subtitle}>{invite.author.email}</div>
                        <div class={styles.subtitle}>ID: {invite.author_id}</div>
                      </td>
                      <td>
                        <div>
                          <strong>{invite.shout.title}</strong>
                        </div>
                        <div class={styles.subtitle}>Автор: {invite.shout.created_by.name}</div>
                        <div class={styles.subtitle}>ID: {invite.shout_id}</div>
                      </td>
                      <td>
                        <span class={`${styles.badge} ${styles[statusDisplay.badge]}`}>
                          {statusDisplay.text}
                        </span>
                      </td>
                      <td>
                        <button
                          class={styles.deleteButton}
                          onClick={() => setDeleteModal({ show: true, invite })}
                          title="Удалить приглашение"
                        >
                          ×
                        </button>
                      </td>
                    </tr>
                  )
                }}
              </For>
            </tbody>
          </table>
        </div>

        <Pagination
          currentPage={pagination().page}
          totalPages={pagination().totalPages}
          total={pagination().total}
          limit={pagination().perPage}
          onPageChange={handlePageChange}
        />
      </Show>

      {/* Модальное окно подтверждения удаления */}
      <Modal
        isOpen={deleteModal().show}
        onClose={() => setDeleteModal({ show: false, invite: null })}
        title="Подтверждение удаления"
        size="small"
      >
        <div class={styles.deleteConfirmation}>
          <p>
            Вы действительно хотите удалить приглашение от{' '}
            <strong>{deleteModal().invite?.inviter.name}</strong> для{' '}
            <strong>{deleteModal().invite?.author.name}</strong> к публикации{' '}
            <strong>"{deleteModal().invite?.shout.title}"</strong>?
          </p>
          <div class={styles.modalActions}>
            <Button variant="secondary" onClick={() => setDeleteModal({ show: false, invite: null })}>
              Отмена
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteModal().invite && deleteInvite(deleteModal().invite!)}
            >
              Удалить
            </Button>
          </div>
        </div>
      </Modal>

      {/* Модальное окно подтверждения пакетного удаления */}
      <Modal
        isOpen={batchDeleteModal().show}
        onClose={() => setBatchDeleteModal({ show: false })}
        title="Подтверждение пакетного удаления"
        size="small"
      >
        <div class={styles.deleteConfirmation}>
          <p>
            Вы действительно хотите удалить <strong>{getSelectedCount()}</strong> выбранных приглашений?
            <br />
            Это действие нельзя отменить.
          </p>
          <div class={styles.modalActions}>
            <Button variant="secondary" onClick={() => setBatchDeleteModal({ show: false })}>
              Отмена
            </Button>
            <Button variant="danger" onClick={deleteSelectedInvites}>
              Удалить выбранные
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default InvitesRoute
