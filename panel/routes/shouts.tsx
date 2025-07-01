import { Component, createSignal, For, onMount, Show } from 'solid-js'
import { query } from '../graphql'
import type { Query, AdminShoutInfo as Shout } from '../graphql/generated/schema'
import { ADMIN_GET_SHOUTS_QUERY } from '../graphql/queries'
import styles from '../styles/Admin.module.css'
import EditableCodePreview from '../ui/EditableCodePreview'
import Modal from '../ui/Modal'
import Pagination from '../ui/Pagination'
import { formatDateRelative } from '../utils/date'

export interface ShoutsRouteProps {
  onError?: (error: string) => void
  onSuccess?: (message: string) => void
}

const ShoutsRoute: Component<ShoutsRouteProps> = (props) => {
  const [shouts, setShouts] = createSignal<Shout[]>([])
  const [loading, setLoading] = createSignal(true)
  const [showBodyModal, setShowBodyModal] = createSignal(false)
  const [selectedShoutBody, setSelectedShoutBody] = createSignal<string>('')
  const [showMediaBodyModal, setShowMediaBodyModal] = createSignal(false)
  const [selectedMediaBody, setSelectedMediaBody] = createSignal<string>('')

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
      const result = await query<{ adminGetShouts: Query['adminGetShouts'] }>(
        `${location.origin}/graphql`,
        ADMIN_GET_SHOUTS_QUERY,
        {
          limit: pagination().limit,
          offset: (pagination().page - 1) * pagination().limit
        }
      )
      if (result?.adminGetShouts?.shouts) {
        setShouts(result.adminGetShouts.shouts)
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

  // Helper functions
  function getShoutStatus(shout: Shout): string {
    if (shout.deleted_at) return '🗑️'
    if (shout.published_at) return '✅'
    return '📝'
  }

  function getShoutStatusTitle(shout: Shout): string {
    if (shout.deleted_at) return 'Удалена'
    if (shout.published_at) return 'Опубликована'
    return 'Черновик'
  }

  function getShoutStatusClass(shout: Shout): string {
    if (shout.deleted_at) return 'status-deleted'
    if (shout.published_at) return 'status-published'
    return 'status-draft'
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
        <div class={styles['shouts-controls']}>
          <div class={styles['search-container']}>
            <div class={styles['search-input-group']}>
              <input
                type="text"
                placeholder="Поиск по заголовку, slug или ID..."
                value={searchQuery()}
                onInput={(e) => setSearchQuery(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    void loadShouts()
                  }
                }}
                class={styles['search-input']}
              />
              <button class={styles['search-button']} onClick={() => void loadShouts()}>
                Поиск
              </button>
            </div>
          </div>
        </div>

        <div class={styles['shouts-list']}>
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
                      <span
                        class={`${styles['status-badge']} ${getShoutStatusClass(shout)}`}
                        title={getShoutStatusTitle(shout)}
                      >
                        {getShoutStatus(shout)}
                      </span>
                    </td>
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
                    <td>{formatDateRelative(shout.created_at)}</td>
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
                                <span class={styles['media-count']}>
                                  {mediaItem?.title || `media[${idx()}]`}
                                </span>
                                <Show when={mediaItem?.body}>
                                  <button
                                    class={styles['edit-button']}
                                    style="padding: 2px 8px; font-size: 12px;"
                                    title="Показать содержимое body"
                                    onClick={() => {
                                      setSelectedMediaBody(mediaItem?.body || '')
                                      setShowMediaBodyModal(true)
                                    }}
                                  >
                                    👁 body
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
        title="Содержимое публикации"
        size="large"
      >
        <EditableCodePreview
          content={selectedShoutBody()}
          maxHeight="85vh"
          onContentChange={(newContent) => {
            setSelectedShoutBody(newContent)
          }}
          onSave={(_content) => {
            // FIXME: добавить логику сохранения изменений в базу данных
            props.onSuccess?.('Содержимое публикации обновлено')
            setShowBodyModal(false)
          }}
          onCancel={() => {
            setShowBodyModal(false)
          }}
          placeholder="Введите содержимое публикации..."
        />
      </Modal>

      <Modal
        isOpen={showMediaBodyModal()}
        onClose={() => setShowMediaBodyModal(false)}
        title="Содержимое media.body"
        size="large"
      >
        <EditableCodePreview
          content={selectedMediaBody()}
          maxHeight="85vh"
          onContentChange={(newContent) => {
            setSelectedMediaBody(newContent)
          }}
          onSave={(_content) => {
            // FIXME: добавить логику сохранения изменений media.body
            props.onSuccess?.('Содержимое media.body обновлено')
            setShowMediaBodyModal(false)
          }}
          onCancel={() => {
            setShowMediaBodyModal(false)
          }}
          placeholder="Введите содержимое media.body..."
        />
      </Modal>
    </div>
  )
}

export default ShoutsRoute
