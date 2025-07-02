import { createEffect, createSignal, For, on, Show } from 'solid-js'
import { Topic, useData } from '../context/data'
import { useTableSort } from '../context/sort'
import { TOPICS_SORT_CONFIG } from '../context/sortConfig'
import TopicEditModal from '../modals/TopicEditModal'
import adminStyles from '../styles/Admin.module.css'
import styles from '../styles/Table.module.css'
import SortableHeader from '../ui/SortableHeader'
import TableControls from '../ui/TableControls'

interface TopicsProps {
  onError?: (message: string) => void
  onSuccess?: (message: string) => void
}

export const Topics = (props: TopicsProps) => {
  const { selectedCommunity, loadTopicsByCommunity, topics: contextTopics } = useData()

  // Состояние поиска
  const [searchQuery, setSearchQuery] = createSignal('')

  // Состояние загрузки
  const [loading, setLoading] = createSignal(false)

  // Модальное окно для редактирования топика
  const [showEditModal, setShowEditModal] = createSignal(false)
  const [selectedTopic, setSelectedTopic] = createSignal<Topic | undefined>(undefined)

  // Сортировка
  const { sortState } = useTableSort()

  /**
   * Загрузка топиков для сообщества
   */
  async function loadTopicsForCommunity() {
    const community = selectedCommunity()
    // selectedCommunity теперь всегда число (по умолчанию 1)

    console.log('[TopicsRoute] Loading all topics for community...')
    try {
      setLoading(true)

      // Загружаем все топики сообщества
      await loadTopicsByCommunity(community!)

      console.log('[TopicsRoute] All topics loaded')
    } catch (error) {
      console.error('[TopicsRoute] Failed to load topics:', error)
      props.onError?.(error instanceof Error ? error.message : 'Не удалось загрузить список топиков')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Обработчик поиска - применяет поисковый запрос
   */
  const handleSearch = () => {
    // Поиск осуществляется через filteredTopics(), которая реагирует на searchQuery()
    // Дополнительная логика поиска здесь не нужна, но можно добавить аналитику
    console.log('[TopicsRoute] Search triggered with query:', searchQuery())
  }

  /**
   * Фильтрация топиков по поисковому запросу
   */
  const filteredTopics = () => {
    const topics = contextTopics()
    const query = searchQuery().toLowerCase()

    if (!query) return topics

    return topics.filter(
      (topic) =>
        topic.title?.toLowerCase().includes(query) ||
        topic.slug?.toLowerCase().includes(query) ||
        topic.id.toString().includes(query)
    )
  }

  /**
   * Сортировка топиков на клиенте
   */
  const sortedTopics = () => {
    const topics = filteredTopics()
    const { field, direction } = sortState()

    return [...topics].sort((a, b) => {
      let comparison = 0

      switch (field) {
        case 'id':
          comparison = a.id - b.id
          break
        case 'title':
          comparison = (a.title || '').localeCompare(b.title || '', 'ru')
          break
        case 'slug':
          comparison = (a.slug || '').localeCompare(b.slug || '', 'ru')
          break
        default:
          comparison = a.id - b.id
      }

      return direction === 'desc' ? -comparison : comparison
    })
  }

  // Загрузка при смене сообщества
  createEffect(
    on(selectedCommunity, (updatedCommunity) => {
      if (updatedCommunity) {
        // selectedCommunity теперь всегда число, поэтому всегда загружаем
        void loadTopicsForCommunity()
      }
    })
  )

  const truncateText = (text: string, maxLength = 100): string => {
    if (!text || text.length <= maxLength) return text
    return `${text.substring(0, maxLength)}...`
  }

  /**
   * Открытие модального окна редактирования топика
   */
  const handleTopicEdit = (topic: Topic) => {
    console.log('[TopicsRoute] Opening edit modal for topic:', topic)
    setSelectedTopic(topic)
    setShowEditModal(true)
  }

  /**
   * Сохранение изменений топика
   */
  const handleTopicSave = (updatedTopic: Topic) => {
    console.log('[TopicsRoute] Saving topic:', updatedTopic)

    // TODO: добавить логику сохранения изменений в базу данных
    // await updateTopic(updatedTopic)

    props.onSuccess?.('Топик успешно обновлён')

    // Обновляем локальные данные (пока что просто перезагружаем)
    void loadTopicsForCommunity()
  }

  /**
   * Обработка ошибок из модального окна
   */
  const handleTopicError = (message: string) => {
    props.onError?.(message)
  }

  /**
   * Рендер строки топика
   */
  const renderTopicRow = (topic: Topic) => (
    <tr
      class={styles.tableRow}
      onClick={() => handleTopicEdit(topic)}
      style="cursor: pointer;"
      title="Нажмите для редактирования топика"
    >
      <td class={styles.tableCell}>{topic.id}</td>
      <td class={styles.tableCell}>
        <strong title={topic.title}>{truncateText(topic.title, 50)}</strong>
      </td>
      <td class={styles.tableCell} title={topic.slug}>
        {truncateText(topic.slug, 30)}
      </td>
      <td class={styles.tableCell}>
        {topic.body ? (
          <span style="color: #666;">{truncateText(topic.body.replace(/<[^>]*>/g, ''), 60)}</span>
        ) : (
          <span style="color: #999; font-style: italic;">Нет содержимого</span>
        )}
      </td>
    </tr>
  )

  return (
    <div class={adminStyles.pageContainer}>
      <TableControls
        searchValue={searchQuery()}
        onSearchChange={setSearchQuery}
        onSearch={handleSearch}
        searchPlaceholder="Поиск по названию, slug или ID..."
        isLoading={loading()}
        onRefresh={loadTopicsForCommunity}
      />

      <div class={styles.tableContainer}>
        <table class={styles.table}>
          <thead>
            <tr class={styles.tableHeader}>
              <SortableHeader field="id" allowedFields={TOPICS_SORT_CONFIG.allowedFields}>
                ID
              </SortableHeader>
              <SortableHeader field="title" allowedFields={TOPICS_SORT_CONFIG.allowedFields}>
                Название
              </SortableHeader>
              <SortableHeader field="slug" allowedFields={TOPICS_SORT_CONFIG.allowedFields}>
                Slug
              </SortableHeader>
              <th class={styles.tableHeaderCell}>Body</th>
            </tr>
          </thead>
          <tbody>
            <Show when={loading()}>
              <tr>
                <td colspan="4" class={styles.loadingCell}>
                  Загрузка...
                </td>
              </tr>
            </Show>
            <Show when={!loading() && sortedTopics().length === 0}>
              <tr>
                <td colspan="4" class={styles.emptyCell}>
                  Нет топиков
                </td>
              </tr>
            </Show>
            <Show when={!loading()}>
              <For each={sortedTopics()}>{renderTopicRow}</For>
            </Show>
          </tbody>
        </table>
      </div>

      {/* Модальное окно для редактирования топика */}
      <TopicEditModal
        isOpen={showEditModal()}
        topic={selectedTopic()!}
        onClose={() => {
          setShowEditModal(false)
          setSelectedTopic(undefined)
        }}
        onSave={handleTopicSave}
        onError={handleTopicError}
      />
    </div>
  )
}
