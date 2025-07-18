import { Component, createEffect, createSignal, For, onMount, Show } from 'solid-js'
import { query } from '../graphql'
import {
  ADMIN_DELETE_REACTION_MUTATION,
  ADMIN_RESTORE_REACTION_MUTATION,
  ADMIN_UPDATE_REACTION_MUTATION
} from '../graphql/mutations'
import { ADMIN_GET_REACTIONS_QUERY } from '../graphql/queries'
import ReactionEditModal from '../modals/ReactionEditModal'
import styles from '../styles/Admin.module.css'
import Button from '../ui/Button'
import Pagination from '../ui/Pagination'
import TableControls from '../ui/TableControls'
import { formatDateRelative } from '../utils/date'

export interface ReactionsRouteProps {
  onError?: (error: string) => void
  onSuccess?: (message: string) => void
}

/**
 * Тип реакции для админки
 */
interface AdminReaction {
  id: number
  kind: string
  body: string
  created_at: number
  updated_at?: number
  deleted_at?: number
  reply_to?: number
  created_by: {
    id: number
    name: string
    email: string
    slug: string
    created_at: number
  }
  shout: {
    id: number
    title: string
    slug: string
    layout: string
    created_at: number
    published_at?: number
    deleted_at?: number
  }
  stat: {
    comments_count: number
    rating: number
  }
}

const ReactionsRoute: Component<ReactionsRouteProps> = (props) => {
  console.log('[ReactionsRoute] Initializing...')
  const [reactions, setReactions] = createSignal<AdminReaction[]>([])
  const [loading, setLoading] = createSignal(true)
  const [selectedReaction, setSelectedReaction] = createSignal<AdminReaction | null>(null)
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

  // Фильтры
  const [searchQuery, setSearchQuery] = createSignal('')
  const [kindFilter, setKindFilter] = createSignal('')
  const [showDeletedOnly, setShowDeletedOnly] = createSignal(false)

  /**
   * Загрузка списка реакций
   */
  async function loadReactions() {
    console.log('[ReactionsRoute] Loading reactions...')
    try {
      setLoading(true)

      // Определяем, является ли поисковый запрос ID публикации
      const query_value = searchQuery().trim()
      const isShoutId = /^\d+$/.test(query_value) // Проверяем, состоит ли запрос только из цифр

      const data = await query<{
        adminGetReactions: {
          reactions: AdminReaction[]
          total: number
          page: number
          perPage: number
          totalPages: number
        }
      }>(`${location.origin}/graphql`, ADMIN_GET_REACTIONS_QUERY, {
        search: isShoutId ? '' : query_value, // Если это ID, не передаем в обычный поиск
        kind: kindFilter() || undefined,
        shout_id: isShoutId ? Number.parseInt(query_value) : undefined, // Если это ID, передаем в shout_id
        status: showDeletedOnly() ? 'deleted' : 'all',
        limit: pagination().limit,
        offset: (pagination().page - 1) * pagination().limit
      })
      if (data?.adminGetReactions?.reactions) {
        console.log('[ReactionsRoute] Reactions loaded:', data.adminGetReactions.reactions.length)
        setReactions(data.adminGetReactions.reactions as AdminReaction[])
        setPagination((prev) => ({
          ...prev,
          total: data.adminGetReactions.total || 0,
          totalPages: data.adminGetReactions.totalPages || 1
        }))
      }
    } catch (error) {
      console.error('[ReactionsRoute] Failed to load reactions:', error)
      props.onError?.(error instanceof Error ? error.message : 'Не удалось загрузить список реакций')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Обновляет реакцию
   */
  async function updateReaction(reactionData: { id: number; body?: string; deleted_at?: number }) {
    try {
      await query(`${location.origin}/graphql`, ADMIN_UPDATE_REACTION_MUTATION, {
        reaction: reactionData
      })

      closeEditModal()
      props.onSuccess?.('Реакция успешно обновлена')
      void loadReactions()
    } catch (err) {
      console.error('Ошибка обновления реакции:', err)
      props.onError?.(err instanceof Error ? err.message : 'Ошибка обновления реакции')
    }
  }

  /**
   * Удаляет реакцию
   */
  async function deleteReaction(id: number) {
    try {
      await query(`${location.origin}/graphql`, ADMIN_DELETE_REACTION_MUTATION, { reaction_id: id })
      props.onSuccess?.('Реакция успешно удалена')
      void loadReactions()
    } catch (err) {
      console.error('Ошибка удаления реакции:', err)
      props.onError?.(err instanceof Error ? err.message : 'Ошибка удаления реакции')
    }
  }

  /**
   * Восстанавливает реакцию
   */
  async function restoreReaction(id: number) {
    try {
      await query(`${location.origin}/graphql`, ADMIN_RESTORE_REACTION_MUTATION, { reaction_id: id })
      props.onSuccess?.('Реакция успешно восстановлена')
      void loadReactions()
    } catch (err) {
      console.error('Ошибка восстановления реакции:', err)
      props.onError?.(err instanceof Error ? err.message : 'Ошибка восстановления реакции')
    }
  }

  function closeEditModal() {
    setShowEditModal(false)
    setSelectedReaction(null)
  }

  // Pagination handlers
  function handlePageChange(page: number) {
    setPagination((prev) => ({ ...prev, page }))
    void loadReactions()
  }

  function handlePerPageChange(limit: number) {
    setPagination((prev) => ({ ...prev, page: 1, limit }))
    void loadReactions()
  }

  // Search handlers
  function handleSearchChange(value: string) {
    setSearchQuery(value)
  }

  function handleSearch() {
    setPagination((prev) => ({ ...prev, page: 1 }))
    void loadReactions()
  }

  // Флаг для пропуска первого вызова createEffect при монтировании
  let isInitialized = false

  // Load reactions on mount
  onMount(() => {
    console.log('[ReactionsRoute] Component mounted, loading reactions...')
    isInitialized = true
    void loadReactions()
  })

  // Автоматически применяем фильтры при изменении (но не при первом рендере)
  createEffect(() => {
    // Отслеживаем изменения фильтров и поиска
    searchQuery()
    kindFilter()
    showDeletedOnly()

    // Пропускаем первый вызов при инициализации
    if (!isInitialized) return

    // Сбрасываем страницу на первую и перезагружаем данные
    setPagination((prev) => ({ ...prev, page: 1 }))
    void loadReactions()
  })

  /**
   * Получает эмоджи для типа реакции
   */
  const getReactionIcon = (kind: string): string => {
    switch (kind) {
      case 'LIKE':
        return '👍'
      case 'DISLIKE':
        return '👎'
      case 'COMMENT':
        return '💬'
      case 'QUOTE':
        return '❝'
      case 'AGREE':
        return '✅'
      case 'DISAGREE':
        return '❌'
      case 'ASK':
        return '❓'
      case 'PROPOSE':
        return '💡'
      case 'PROOF':
        return '🔬'
      case 'DISPROOF':
        return '🚫'
      case 'ACCEPT':
        return '✔️'
      case 'REJECT':
        return '❌'
      case 'CREDIT':
        return '🎨'
      case 'SILENT':
        return '🤫'
      default:
        return '💬'
    }
  }

  /**
   * Получает название типа реакции на русском
   */
  const getReactionName = (kind: string): string => {
    switch (kind) {
      case 'LIKE':
        return 'Лайк'
      case 'DISLIKE':
        return 'Дизлайк'
      case 'COMMENT':
        return 'Комментарий'
      case 'QUOTE':
        return 'Цитата'
      case 'AGREE':
        return 'Согласен'
      case 'DISAGREE':
        return 'Не согласен'
      case 'ASK':
        return 'Вопрос'
      case 'PROPOSE':
        return 'Предложение'
      case 'PROOF':
        return 'Доказательство'
      case 'DISPROOF':
        return 'Опровержение'
      case 'ACCEPT':
        return 'Принять'
      case 'REJECT':
        return 'Отклонить'
      case 'CREDIT':
        return 'Упоминание'
      case 'SILENT':
        return 'Причастность'
      default:
        return kind
    }
  }

  /**
   * Получает название статуса реакции
   */
  const getReactionStatusTitle = (reaction: AdminReaction): string => {
    return reaction.deleted_at ? 'Удалена' : 'Активна'
  }

  /**
   * Получает цвет фона для ID реакции в зависимости от статуса
   */
  const getReactionStatusBackgroundColor = (reaction: AdminReaction): string => {
    return reaction.deleted_at ? '#fee2e2' : '#d1fae5' // Пастельный красный для удаленных, зеленый для активных
  }

  /**
   * Форматирует tooltip для автора с email и датой регистрации
   */
  const formatAuthorTooltip = (author: { email?: string | null; created_at?: number | null }): string => {
    if (!author.email) return ''
    if (!author.created_at) return author.email

    const registrationDate = new Date(author.created_at * 1000).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
    return `${author.email} с ${registrationDate}`
  }

  return (
    <div class={styles['reactions-container']}>
      <Show when={loading()}>
        <div class={styles['loading']}>Загрузка данных...</div>
      </Show>

      <Show when={!loading()}>
        <div class={styles['filters-section']}>
          <TableControls
            searchValue={searchQuery()}
            onSearchChange={handleSearchChange}
            onSearch={handleSearch}
            searchPlaceholder="Поиск по тексту, автору, публикации или ID публикации..."
            isLoading={loading()}
          />

          <div class={styles['additional-filters']}>
            <select
              value={kindFilter()}
              onChange={(e) => setKindFilter(e.target.value)}
              class={styles['filter-select']}
            >
              <option value="">Все типы</option>
              <option value="LIKE">Лайк</option>
              <option value="DISLIKE">Дизлайк</option>
              <option value="COMMENT">Комментарий</option>
              <option value="QUOTE">Цитата</option>
              <option value="AGREE">Согласен</option>
              <option value="DISAGREE">Не согласен</option>
              <option value="ASK">Вопрос</option>
              <option value="PROPOSE">Предложение</option>
              <option value="PROOF">Доказательство</option>
              <option value="DISPROOF">Опровержение</option>
              <option value="ACCEPT">Принять</option>
              <option value="REJECT">Отклонить</option>
              <option value="CREDIT">Упоминание</option>
              <option value="SILENT">Причастность</option>
            </select>

            <label class={styles['filter-checkbox']}>
              <input
                type="checkbox"
                checked={showDeletedOnly()}
                onChange={(e) => setShowDeletedOnly(e.target.checked)}
              />
              Только удаленные
            </label>
          </div>
        </div>

        <Show when={reactions().length === 0}>
          <div class={styles['empty-state']}>Нет данных для отображения</div>
        </Show>

        <Show when={reactions().length > 0}>
          <div class={styles['reactions-list']}>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Тип</th>
                  <th>Текст</th>
                  <th>Автор</th>
                  <th>Публикация</th>
                  <th>Создано</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                <For each={reactions()}>
                  {(reaction) => (
                    <tr
                      class={reaction.deleted_at ? styles['deleted-row'] : ''}
                      onClick={() => {
                        setSelectedReaction(reaction)
                        setShowEditModal(true)
                      }}
                    >
                      <td
                        style={{
                          'background-color': getReactionStatusBackgroundColor(reaction),
                          padding: '8px 12px',
                          'border-radius': '4px'
                        }}
                        title={getReactionStatusTitle(reaction)}
                      >
                        {reaction.id}
                      </td>
                      <td>
                        <span title={getReactionName(reaction.kind)} class={styles['reaction-icon']}>
                          {getReactionIcon(reaction.kind)}
                        </span>
                      </td>
                      <td class={styles['body-cell']}>
                        <div class={styles['body-preview']}>
                          {reaction.body
                            ? reaction.body.substring(0, 100) + (reaction.body.length > 100 ? '...' : '')
                            : '-'}
                        </div>
                      </td>
                      <td>
                        <div class={styles['author-cell']} title={formatAuthorTooltip(reaction.created_by)}>
                          <div>{reaction.created_by.name || 'Без имени'}</div>
                          <div class={styles['author-email']}>{reaction.created_by.email}</div>
                        </div>
                      </td>
                      <td>
                        <div class={styles['shout-cell']}>
                          <div class={styles['shout-title']}>
                            {reaction.shout.title.substring(0, 50)}
                            {reaction.shout.title.length > 50 ? '...' : ''}
                          </div>
                          <div class={styles['shout-meta']}>
                            ID: {reaction.shout.id} | {reaction.shout.slug}
                          </div>
                        </div>
                      </td>
                      <td>{formatDateRelative(reaction.created_at)()}</td>
                      <td>
                        <div class={styles['actions-cell']} onClick={(e) => e.stopPropagation()}>
                          <Show when={reaction.deleted_at}>
                            <Button
                              variant="primary"
                              size="small"
                              onClick={() => restoreReaction(reaction.id)}
                            >
                              Восстановить
                            </Button>
                          </Show>
                          <Show when={!reaction.deleted_at}>
                            <Button
                              variant="danger"
                              size="small"
                              onClick={() => deleteReaction(reaction.id)}
                            >
                              Удалить
                            </Button>
                          </Show>
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
      </Show>

      <Show when={showEditModal() && selectedReaction()}>
        <ReactionEditModal
          reaction={selectedReaction()!}
          isOpen={showEditModal()}
          onClose={closeEditModal}
          onSave={updateReaction}
        />
      </Show>
    </div>
  )
}

export default ReactionsRoute
