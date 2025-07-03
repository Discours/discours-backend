import { createEffect, createSignal, For, on, onMount, Show, untrack } from 'solid-js'
import { useData } from '../context/data'
import { useTableSort } from '../context/sort'
import { SHOUTS_SORT_CONFIG } from '../context/sortConfig'
import { query } from '../graphql'
import type { Query, AdminShoutInfo as Shout } from '../graphql/generated/schema'
import { ADMIN_GET_SHOUTS_QUERY } from '../graphql/queries'
import styles from '../styles/Admin.module.css'
import HTMLEditor from '../ui/HTMLEditor'
import Modal from '../ui/Modal'
import Pagination from '../ui/Pagination'
import SortableHeader from '../ui/SortableHeader'
import TableControls from '../ui/TableControls'
import { formatDateRelative } from '../utils/date'

export interface ShoutsRouteProps {
  onError?: (error: string) => void
  onSuccess?: (message: string) => void
}

const ShoutsRoute = (props: ShoutsRouteProps) => {
  const [shouts, setShouts] = createSignal<Shout[]>([])
  const [loading, setLoading] = createSignal(true)
  const [showBodyModal, setShowBodyModal] = createSignal(false)
  const [selectedShoutBody, setSelectedShoutBody] = createSignal<string>('')
  const [showMediaBodyModal, setShowMediaBodyModal] = createSignal(false)
  const [selectedMediaBody, setSelectedMediaBody] = createSignal<string>('')
  const { sortState } = useTableSort()
  const { selectedCommunity } = useData()

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
    totalPages: 0
  })

  // Filter state
  const [searchQuery, setSearchQuery] = createSignal('')

  /**
   * Загрузка списка публикаций
   */
  async function loadShouts() {
    try {
      setLoading(true)

      // Подготавливаем параметры запроса
      const variables: {
        limit: number
        offset: number
        search?: string
        community?: number
      } = {
        limit: pagination().limit,
        offset: (pagination().page - 1) * pagination().limit
      }

      // Добавляем поиск если есть
      if (searchQuery().trim()) {
        variables.search = searchQuery().trim()
      }

      // Добавляем фильтр по сообществу если выбрано
      const communityFilter = selectedCommunity()
      if (communityFilter !== null) {
        variables.community = communityFilter
      }

      const result = await query<{ adminGetShouts: Query['adminGetShouts'] }>(
        `${location.origin}/graphql`,
        ADMIN_GET_SHOUTS_QUERY,
        variables
      )
      if (result?.adminGetShouts?.shouts) {
        // Применяем сортировку на клиенте
        const sortedShouts = sortShouts(result.adminGetShouts.shouts)
        setShouts(sortedShouts)
        setPagination((prev) => ({
          ...prev,
          total: result.adminGetShouts.total || 0,
          totalPages: result.adminGetShouts.totalPages || 1
        }))
      }
    } catch (error) {
      console.error('Failed to load shouts:', error)
      props.onError?.(error instanceof Error ? error.message : 'Failed to load shouts')
    } finally {
      setLoading(false)
    }
  }

  // Load shouts on mount
  onMount(() => {
    void loadShouts()
  })

  // Pagination handlers
  function handlePageChange(page: number) {
    setPagination((prev) => ({ ...prev, page }))
    void loadShouts()
  }

  function handlePerPageChange(limit: number) {
    setPagination((prev) => ({ ...prev, page: 1, limit }))
    void loadShouts()
  }

  /**
   * Сортирует публикации на клиенте
   */
  function sortShouts(shoutsData: Shout[]): Shout[] {
    const { field, direction } = sortState()

    return [...shoutsData].sort((a, b) => {
      let comparison = 0

      switch (field) {
        case 'id':
          comparison = Number(a.id) - Number(b.id)
          break
        case 'title':
          comparison = (a.title || '').localeCompare(b.title || '', 'ru')
          break
        case 'slug':
          comparison = (a.slug || '').localeCompare(b.slug || '', 'ru')
          break
        case 'created_at':
          comparison = (a.created_at || 0) - (b.created_at || 0)
          break
        case 'published_at':
          comparison = (a.published_at || 0) - (b.published_at || 0)
          break
        case 'updated_at':
          comparison = (a.updated_at || 0) - (b.updated_at || 0)
          break
        default:
          comparison = Number(a.id) - Number(b.id)
      }

      return direction === 'desc' ? -comparison : comparison
    })
  }

  // Пересортировка при изменении состояния сортировки
  createEffect(
    on([sortState], () => {
      if (shouts().length > 0) {
        // Используем untrack для предотвращения бесконечной рекурсии
        const currentShouts = untrack(() => shouts())
        const sortedShouts = sortShouts(currentShouts)

        // Сравниваем текущий порядок с отсортированным, чтобы избежать лишних обновлений
        const needsUpdate =
          JSON.stringify(currentShouts.map((s: Shout) => s.id)) !==
          JSON.stringify(sortedShouts.map((s: Shout) => s.id))

        if (needsUpdate) {
          setShouts(sortedShouts)
        }
      }
    })
  )

  // Перезагрузка при изменении выбранного сообщества
  createEffect(
    on([selectedCommunity], () => {
      void loadShouts()
    })
  )

  // Helper functions
  function getShoutStatusTitle(shout: Shout): string {
    if (shout.deleted_at) return 'Удалена'
    if (shout.published_at) return 'Опубликована'
    return 'Черновик'
  }

  function getShoutStatusBackgroundColor(shout: Shout): string {
    if (shout.deleted_at) return '#fee2e2' // Пастельный красный
    if (shout.published_at) return '#d1fae5' // Пастельный зеленый
    return '#fef3c7' // Пастельный желтый для черновиков
  }

  function truncateText(text: string, maxLength = 100): string {
    if (!text || text.length <= maxLength) return text
    return `${text.substring(0, maxLength)}...`
  }

  return (
    <div class={styles['shouts-container']}>
      <Show when={loading()}>
        <div class={styles['loading']}>Загрузка публикаций...</div>
      </Show>

      <Show when={!loading() && shouts().length === 0}>
        <div class={styles['empty-state']}>Нет публикаций для отображения</div>
      </Show>

      <Show when={!loading() && shouts().length > 0}>
        <TableControls
          onRefresh={loadShouts}
          isLoading={loading()}
          searchValue={searchQuery()}
          onSearchChange={(value) => setSearchQuery(value)}
          onSearch={() => void loadShouts()}
        />

        <div class={styles['shouts-list']}>
          <table>
            <thead>
              <tr>
                <SortableHeader field="id" allowedFields={SHOUTS_SORT_CONFIG.allowedFields}>
                  ID
                </SortableHeader>
                <SortableHeader field="title" allowedFields={SHOUTS_SORT_CONFIG.allowedFields}>
                  Заголовок
                </SortableHeader>
                <SortableHeader field="slug" allowedFields={SHOUTS_SORT_CONFIG.allowedFields}>
                  Slug
                </SortableHeader>
                <th>Авторы</th>
                <th>Темы</th>

                <SortableHeader field="created_at" allowedFields={SHOUTS_SORT_CONFIG.allowedFields}>
                  Создан
                </SortableHeader>
                <th>Содержимое</th>
                <th>Media</th>
              </tr>
            </thead>
            <tbody>
              <For each={shouts()}>
                {(shout) => (
                  <tr>
                    <td
                      style={{
                        'background-color': getShoutStatusBackgroundColor(shout),
                        padding: '8px 12px',
                        'border-radius': '4px'
                      }}
                      title={getShoutStatusTitle(shout)}
                    >
                      {shout.id}
                    </td>
                    <td title={shout.title}>{truncateText(shout.title, 50)}</td>
                    <td title={shout.slug}>{truncateText(shout.slug, 30)}</td>
                    <td>
                      <Show when={shout.authors?.length}>
                        <div class={styles['authors-list']}>
                          <For each={shout.authors}>
                            {(author) => (
                              <Show when={author}>
                                {(safeAuthor) => (
                                  <span class={styles['author-badge']} title={safeAuthor()?.email || ''}>
                                    {safeAuthor()?.name || safeAuthor()?.email || `ID:${safeAuthor()?.id}`}
                                  </span>
                                )}
                              </Show>
                            )}
                          </For>
                        </div>
                      </Show>
                      <Show when={!shout.authors?.length}>
                        <span class={styles['no-data']}>-</span>
                      </Show>
                    </td>
                    <td>
                      <Show when={shout.topics?.length}>
                        <div class={styles['topics-list']}>
                          <For each={shout.topics}>
                            {(topic) => (
                              <Show when={topic}>
                                {(safeTopic) => (
                                  <span class={styles['topic-badge']} title={safeTopic()?.slug || ''}>
                                    {safeTopic()?.title || safeTopic()?.slug}
                                  </span>
                                )}
                              </Show>
                            )}
                          </For>
                        </div>
                      </Show>
                      <Show when={!shout.topics?.length}>
                        <span class={styles['no-data']}>-</span>
                      </Show>
                    </td>

                    <td>{formatDateRelative(shout.created_at)()}</td>
                    <td
                      class={styles['body-cell']}
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
                                <Show when={mediaItem?.body}>
                                  <button
                                    class={styles['edit-button']}
                                    style="padding: 4px; font-size: 14px; min-width: 24px; border-radius: 4px;"
                                    onClick={() => {
                                      setSelectedMediaBody(mediaItem?.body || '')
                                      setShowMediaBodyModal(true)
                                    }}
                                    title={mediaItem?.title || idx().toString()}
                                  >
                                    👁
                                  </button>
                                </Show>
                              </div>
                            )}
                          </For>
                        </div>
                      </Show>
                      <Show when={!shout.media || shout.media.length === 0}>
                        <span class={styles['no-data']}>-</span>
                      </Show>
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
        </div>
      </Show>

      <Modal
        isOpen={showBodyModal()}
        onClose={() => setShowBodyModal(false)}
        title="Редактирование содержимого публикации"
        size="large"
        footer={
          <>
            <button
              type="button"
              class={`${styles.button} ${styles.secondary}`}
              onClick={() => setShowBodyModal(false)}
            >
              Отмена
            </button>
            <button
              type="button"
              class={`${styles.button} ${styles.primary}`}
              onClick={() => {
                // TODO: добавить логику сохранения изменений в базу данных
                props.onSuccess?.('Содержимое публикации обновлено')
                setShowBodyModal(false)
              }}
            >
              Сохранить
            </button>
          </>
        }
      >
        <div style="padding: 1rem;">
          <HTMLEditor
            value={selectedShoutBody()}
            onInput={(value) => setSelectedShoutBody(value)}
          />
        </div>
      </Modal>

      <Modal
        isOpen={showMediaBodyModal()}
        onClose={() => setShowMediaBodyModal(false)}
        title="Редактирование содержимого media.body"
        size="large"
        footer={
          <>
            <button
              type="button"
              class={`${styles.button} ${styles.secondary}`}
              onClick={() => setShowMediaBodyModal(false)}
            >
              Отмена
            </button>
            <button
              type="button"
              class={`${styles.button} ${styles.primary}`}
              onClick={() => {
                // TODO: добавить логику сохранения изменений media.body
                props.onSuccess?.('Содержимое media.body обновлено')
                setShowMediaBodyModal(false)
              }}
            >
              Сохранить
            </button>
          </>
        }
      >
        <div style="padding: 1rem;">
          <HTMLEditor
            value={selectedMediaBody()}
            onInput={(value) => setSelectedMediaBody(value)}
          />gjl
        </div>
      </Modal>
    </div>
  )
}

export default ShoutsRoute
