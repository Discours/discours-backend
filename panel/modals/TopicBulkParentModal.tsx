import { Component, createSignal, For, Show } from 'solid-js'
import styles from '../styles/Form.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

interface Topic {
  id: number
  title: string
  slug: string
  parent_ids?: number[]
  community: number
}

interface TopicBulkParentModalProps {
  isOpen: boolean
  onClose: () => void
  selectedTopicIds: number[]
  allTopics: Topic[]
  onSave: (changes: BulkParentChange[]) => void
  onError: (error: string) => void
}

interface BulkParentChange {
  topicId: number
  newParentIds: number[]
  oldParentIds: number[]
}

const TopicBulkParentModal: Component<TopicBulkParentModalProps> = (props) => {
  const [newParentId, setNewParentId] = createSignal<number | null>(null)
  const [searchQuery, setSearchQuery] = createSignal('')
  const [actionType, setActionType] = createSignal<'set' | 'makeRoot'>('set')

  // Получаем выбранные топики
  const getSelectedTopics = () => {
    return props.allTopics.filter((topic) => props.selectedTopicIds.includes(topic.id))
  }

  // Фильтрация доступных родителей
  const getAvailableParents = () => {
    const selectedIds = new Set(props.selectedTopicIds)

    return props.allTopics.filter((topic) => {
      // Исключаем выбранные топики
      if (selectedIds.has(topic.id)) return false

      // Исключаем топики, которые являются детьми выбранных
      const isChildOfSelected = props.selectedTopicIds.some((selectedId) =>
        isDescendant(selectedId, topic.id)
      )
      if (isChildOfSelected) return false

      // Фильтр по поисковому запросу
      const query = searchQuery().toLowerCase()
      if (query && !topic.title.toLowerCase().includes(query)) return false

      return true
    })
  }

  // Проверка, является ли топик потомком другого
  const isDescendant = (ancestorId: number, descendantId: number): boolean => {
    const descendant = props.allTopics.find((t) => t.id === descendantId)
    if (!descendant || !descendant.parent_ids) return false

    return descendant.parent_ids.includes(ancestorId)
  }

  // Получение пути к корню
  const getTopicPath = (topicId: number): string => {
    const topic = props.allTopics.find((t) => t.id === topicId)
    if (!topic) return ''

    if (!topic.parent_ids || topic.parent_ids.length === 0) {
      return topic.title
    }

    const parentPath = getTopicPath(topic.parent_ids[topic.parent_ids.length - 1])
    return `${parentPath} → ${topic.title}`
  }

  // Группировка топиков по сообществам
  const getTopicsByCommunity = () => {
    const selectedTopics = getSelectedTopics()
    const communities = new Map<number, Topic[]>()

    selectedTopics.forEach((topic) => {
      if (!communities.has(topic.community)) {
        communities.set(topic.community, [])
      }
      communities.get(topic.community)!.push(topic)
    })

    return communities
  }

  // Проверка совместимости действия
  const validateAction = (): string | null => {
    const communities = getTopicsByCommunity()

    if (communities.size > 1) {
      return 'Нельзя изменять иерархию тем из разных сообществ одновременно'
    }

    if (actionType() === 'set' && !newParentId()) {
      return 'Выберите родительскую тему'
    }

    const selectedParent = props.allTopics.find((t) => t.id === newParentId())
    if (selectedParent) {
      const selectedCommunity = Array.from(communities.keys())[0]
      if (selectedParent.community !== selectedCommunity) {
        return 'Родительская тема должна быть из того же сообщества'
      }
    }

    return null
  }

  // Сохранение изменений
  const handleSave = () => {
    const validationError = validateAction()
    if (validationError) {
      props.onError(validationError)
      return
    }

    const changes: BulkParentChange[] = []
    const selectedTopics = getSelectedTopics()

    selectedTopics.forEach((topic) => {
      let newParentIds: number[] = []

      if (actionType() === 'set' && newParentId()) {
        const parentTopic = props.allTopics.find((t) => t.id === newParentId())
        if (parentTopic) {
          newParentIds = [...(parentTopic.parent_ids || []), newParentId()!]
        }
      }

      changes.push({
        topicId: topic.id,
        newParentIds,
        oldParentIds: topic.parent_ids || []
      })
    })

    props.onSave(changes)
  }

  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={`Массовое изменение иерархии (${props.selectedTopicIds.length} тем)`}
      size="large"
    >
      <div class={styles.bulkParentContainer}>
        {/* Проверка совместимости */}
        <Show when={getTopicsByCommunity().size > 1}>
          <div class={styles.errorMessage}>
            ⚠️ Выбраны темы из разных сообществ. Массовое изменение иерархии возможно только для тем одного
            сообщества.
          </div>
        </Show>

        {/* Список выбранных тем */}
        <div class={styles.selectedTopicsPreview}>
          <h4>Выбранные темы ({props.selectedTopicIds.length}):</h4>
          <div class={styles.topicsList}>
            <For each={getSelectedTopics()}>
              {(topic) => (
                <div class={styles.topicPreviewItem}>
                  <span class={styles.topicTitle}>{topic.title}</span>
                  <span class={styles.topicId}>#{topic.id}</span>
                  <Show when={topic.parent_ids && topic.parent_ids.length > 0}>
                    <div class={styles.currentPath}>Текущий путь: {getTopicPath(topic.id)}</div>
                  </Show>
                </div>
              )}
            </For>
          </div>
        </div>

        {/* Выбор действия */}
        <div class={styles.actionSelection}>
          <h4>Выберите действие:</h4>
          <div class={styles.actionOptions}>
            <div class={styles.actionOption}>
              <input
                type="radio"
                id="action-set"
                name="action"
                checked={actionType() === 'set'}
                onChange={() => setActionType('set')}
              />
              <label for="action-set" class={styles.actionLabel}>
                <strong>Установить нового родителя</strong>
                <div class={styles.actionDescription}>
                  Переместить все выбранные темы под одного родителя
                </div>
              </label>
            </div>

            <div class={styles.actionOption}>
              <input
                type="radio"
                id="action-root"
                name="action"
                checked={actionType() === 'makeRoot'}
                onChange={() => setActionType('makeRoot')}
              />
              <label for="action-root" class={styles.actionLabel}>
                <strong>🏠 Сделать корневыми</strong>
                <div class={styles.actionDescription}>
                  Переместить все выбранные темы на верхний уровень
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* Выбор родителя */}
        <Show when={actionType() === 'set'}>
          <div class={styles.parentSelection}>
            <h4>Выбор родительской темы:</h4>

            <div class={styles.searchSection}>
              <input
                type="text"
                value={searchQuery()}
                onInput={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск родительской темы..."
                class={styles.searchInput}
              />
            </div>

            <div class={styles.parentsList}>
              <For each={getAvailableParents()}>
                {(topic) => (
                  <div class={styles.parentOption}>
                    <input
                      type="radio"
                      id={`bulk-parent-${topic.id}`}
                      name="bulk-parent"
                      checked={newParentId() === topic.id}
                      onChange={() => setNewParentId(topic.id)}
                    />
                    <label for={`bulk-parent-${topic.id}`} class={styles.parentOptionLabel}>
                      <strong>{topic.title}</strong>
                      <div class={styles.parentDescription}>
                        <span class={styles.topicId}>#{topic.id}</span>
                        <span class={styles.topicSlug}>{topic.slug}</span>
                      </div>
                      <Show when={topic.parent_ids && topic.parent_ids.length > 0}>
                        <div class={styles.parentPath}>Текущий путь: {getTopicPath(topic.id)}</div>
                      </Show>
                    </label>
                  </div>
                )}
              </For>
            </div>

            <Show when={getAvailableParents().length === 0}>
              <div class={styles.noResults}>
                {searchQuery()
                  ? `Нет доступных тем для поиска "${searchQuery()}"`
                  : 'Нет доступных родительских тем'}
              </div>
            </Show>
          </div>
        </Show>

        {/* Предварительный просмотр изменений */}
        <Show when={actionType() === 'makeRoot' || (actionType() === 'set' && newParentId())}>
          <div class={styles.previewSection}>
            <h4>Предварительный просмотр:</h4>
            <div class={styles.previewChanges}>
              <For each={getSelectedTopics()}>
                {(topic) => (
                  <div class={styles.previewItem}>
                    <strong>{topic.title}</strong>
                    <div class={styles.previewChange}>
                      <span class={styles.beforeState}>
                        Было: {topic.parent_ids?.length ? getTopicPath(topic.id) : 'Корневая тема'}
                      </span>
                      <span class={styles.arrow}>→</span>
                      <span class={styles.afterState}>
                        Станет:{' '}
                        {actionType() === 'makeRoot'
                          ? 'Корневая тема'
                          : newParentId()
                            ? `${getTopicPath(newParentId()!)} → ${topic.title}`
                            : ''}
                      </span>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </div>
        </Show>

        <div class={styles.modalActions}>
          <Button variant="secondary" onClick={props.onClose}>
            Отмена
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={!!validateAction() || getTopicsByCommunity().size > 1}
          >
            Применить к {props.selectedTopicIds.length} темам
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default TopicBulkParentModal
