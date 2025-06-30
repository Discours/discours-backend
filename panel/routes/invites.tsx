import { Component, createSignal, For, onMount, Show } from 'solid-js'
import {
  ADMIN_CREATE_INVITE_MUTATION,
  ADMIN_DELETE_INVITE_MUTATION,
  ADMIN_UPDATE_INVITE_MUTATION
} from '../graphql/mutations'
import { ADMIN_GET_INVITES_QUERY } from '../graphql/queries'
import InviteEditModal from '../modals/InviteEditModal'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import Pagination from '../ui/Pagination'
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
    perPage: 10,
    total: 0,
    totalPages: 1
  })

  const [editModal, setEditModal] = createSignal<{ show: boolean; invite: Invite | null }>({
    show: false,
    invite: null
  })
  const [deleteModal, setDeleteModal] = createSignal<{ show: boolean; invite: Invite | null }>({
    show: false,
    invite: null
  })
  const [createModal, setCreateModal] = createSignal<{ show: boolean }>({
    show: false
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
        perPage: data.perPage || 10,
        total: data.total || 0,
        totalPages: data.totalPages || 1
      })
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
   * Открывает модалку создания
   */
  const openCreateModal = () => {
    setCreateModal({ show: true })
  }

  /**
   * Открывает модалку редактирования
   */
  const openEditModal = (invite: Invite) => {
    setEditModal({ show: true, invite })
  }

  /**
   * Обрабатывает сохранение приглашения (создание или обновление)
   */
  const handleSaveInvite = async (inviteData: Partial<Invite>) => {
    try {
      const isCreating = !editModal().invite && createModal().show
      const mutation = isCreating ? ADMIN_CREATE_INVITE_MUTATION : ADMIN_UPDATE_INVITE_MUTATION

      // Получаем токен авторизации из localStorage или cookie
      const authToken = localStorage.getItem('auth_token') || getAuthTokenFromCookie()
      console.log(`[InvitesRoute] Сохранение приглашения, токен: ${authToken ? 'найден' : 'не найден'}`)

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authToken ? `Bearer ${authToken}` : ''
        },
        body: JSON.stringify({
          query: mutation,
          variables: { invite: inviteData }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const resultData = isCreating ? result.data.adminCreateInvite : result.data.adminUpdateInvite
      if (!resultData.success) {
        throw new Error(resultData.error || 'Неизвестная ошибка')
      }

      props.onSuccess(isCreating ? 'Приглашение успешно создано' : 'Приглашение успешно обновлено')
      setCreateModal({ show: false })
      setEditModal({ show: false, invite: null })
      await loadInvites(pagination().page)
    } catch (error) {
      props.onError(
        `Ошибка ${createModal().show ? 'создания' : 'обновления'} приглашения: ${(error as Error).message}`
      )
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

  // Загружаем приглашения при монтировании компонента
  onMount(() => {
    void loadInvites()
  })

  return (
    <div class={styles.container}>
      <div class={styles.header}>
        <div class={styles.controls}>
          <input
            type="text"
            placeholder="Поиск приглашений..."
            value={search()}
            onInput={(e) => setSearch(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            class={styles.searchInput}
          />
          <Button onClick={handleSearch} disabled={loading()}>
            🔍
          </Button>

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

          <Button onClick={() => loadInvites(pagination().page)} disabled={loading()}>
            {loading() ? 'Загрузка...' : 'Обновить'}
          </Button>
        </div>

        <Button variant="primary" onClick={openCreateModal}>
          Создать приглашение
        </Button>
      </div>

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
                <th>Приглашающий</th>
                <th>Приглашаемый</th>
                <th>Публикация</th>
                <th>Статус</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              <For each={invites()}>
                {(invite) => {
                  const statusDisplay = getStatusDisplay(invite.status)
                  return (
                    <tr
                      class={styles.clickableRow}
                      onClick={() => openEditModal(invite)}
                      title="Нажмите для редактирования"
                    >
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
                          onClick={(e) => {
                            e.stopPropagation()
                            setDeleteModal({ show: true, invite })
                          }}
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

      {/* Модальные окна */}
      <InviteEditModal
        isOpen={createModal().show}
        invite={null}
        onClose={() => setCreateModal({ show: false })}
        onSave={handleSaveInvite}
      />

      <InviteEditModal
        isOpen={editModal().show}
        invite={editModal().invite}
        onClose={() => setEditModal({ show: false, invite: null })}
        onSave={handleSaveInvite}
      />

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
    </div>
  )
}

export default InvitesRoute
