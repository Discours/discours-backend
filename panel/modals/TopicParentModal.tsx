import { Component, createSignal, For, Show } from 'solid-js'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import styles from '../styles/Form.module.css'

interface Topic {
  id: number
  title: string
  slug: string
  parent_ids?: number[]
  community: number
}

interface TopicParentModalProps {
  isOpen: boolean
  onClose: () => void
  topic: Topic | null
  allTopics: Topic[]
  onSave: (topic: Topic) => void
  onError: (error: string) => void
}

const TopicParentModal: Component<TopicParentModalProps> = (props) => {
  const [selectedParentId, setSelectedParentId] = createSignal<number | null>(null)
  const [searchQuery, setSearchQuery] = createSignal('')

  // Получаем текущего родителя при открытии модалки
  const getCurrentParentId = (): number | null => {
    const topic = props.topic
    if (!topic || !topic.parent_ids || topic.parent_ids.length === 0) {
      return null
    }
    return topic.parent_ids[topic.parent_ids.length - 1]
  }

  // Фильтрация доступных родителей
  const getAvailableParents = () => {
    const currentTopic = props.topic
    if (!currentTopic) return []

    return props.allTopics.filter(topic => {
      // Исключаем сам топик
      if (topic.id === currentTopic.id) return false

      // Исключаем топики из других сообществ
      if (topic.community !== currentTopic.community) return false

      // Исключаем дочерние топики (предотвращаем циклы)
      if (isDescendant(currentTopic.id, topic.id)) return false

      // Фильтр по поисковому запросу
      const query = searchQuery().toLowerCase()
      if (query && !topic.title.toLowerCase().includes(query)) return false

      return true
    })
  }

  // Проверка, является ли топик потомком другого
  const isDescendant = (ancestorId: number, descendantId: number): boolean => {
    const descendant = props.allTopics.find(t => t.id === descendantId)
    if (!descendant || !descendant.parent_ids) return false

    return descendant.parent_ids.includes(ancestorId)
  }

  // Получение пути к корню для отображения полного пути
  const getTopicPath = (topicId: number): string => {
    const topic = props.allTopics.find(t => t.id === topicId)
    if (!topic) return ''

    if (!topic.parent_ids || topic.parent_ids.length === 0) {
      return topic.title
    }

    const parentPath = getTopicPath(topic.parent_ids[topic.parent_ids.length - 1])
    return `${parentPath} → ${topic.title}`
  }

  // Сохранение изменений
  const handleSave = () => {
    const currentTopic = props.topic
    if (!currentTopic) return

    const newParentId = selectedParentId()
    let newParentIds: number[] = []

    if (newParentId) {
      const parentTopic = props.allTopics.find(t => t.id === newParentId)
      if (parentTopic) {
        // Строим полный путь от корня до нового родителя
        newParentIds = [...(parentTopic.parent_ids || []), newParentId]
      }
    }

    const updatedTopic: Topic = {
      ...currentTopic,
      parent_ids: newParentIds
    }

    props.onSave(updatedTopic)
  }

  // Инициализация при открытии
  if (props.isOpen && props.topic) {
    setSelectedParentId(getCurrentParentId())
    setSearchQuery('')
  }

  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={`Выбор родительской темы для "${props.topic?.title}"`}
    >
      <div class={styles.parentSelectorContainer}>
        <div class={styles.searchSection}>
          <label class={styles.label}>Поиск родительской темы:</label>
          <input
            type="text"
            value={searchQuery()}
            onInput={(e) => setSearchQuery(e.target.value)}
            placeholder="Введите название темы..."
            class={styles.searchInput}
          />
        </div>

        <div class={styles.currentSelection}>
          <label class={styles.label}>Текущий родитель:</label>
          <div class={styles.currentParent}>
            <Show
              when={getCurrentParentId()}
              fallback={<span class={styles.noParent}>Корневая тема</span>}
            >
              <span class={styles.parentPath}>
                {getCurrentParentId() ? getTopicPath(getCurrentParentId()!) : ''}
              </span>
            </Show>
          </div>
        </div>

        <div class={styles.parentOptions}>
          <label class={styles.label}>Выберите нового родителя:</label>

          {/* Опция "Сделать корневой" */}
          <div class={styles.parentOption}>
            <input
              type="radio"
              id="root-option"
              name="parent"
              checked={selectedParentId() === null}
              onChange={() => setSelectedParentId(null)}
            />
            <label for="root-option" class={styles.parentOptionLabel}>
              <strong>🏠 Корневая тема</strong>
              <div class={styles.parentDescription}>
                Переместить на верхний уровень иерархии
              </div>
            </label>
          </div>

          {/* Доступные родители */}
          <div class={styles.parentsList}>
            <For each={getAvailableParents()}>
              {(topic) => (
                <div class={styles.parentOption}>
                  <input
                    type="radio"
                    id={`parent-${topic.id}`}
                    name="parent"
                    checked={selectedParentId() === topic.id}
                    onChange={() => setSelectedParentId(topic.id)}
                  />
                  <label for={`parent-${topic.id}`} class={styles.parentOptionLabel}>
                    <strong>{topic.title}</strong>
                    <div class={styles.parentDescription}>
                      <span class={styles.topicId}>#{topic.id}</span>
                      <span class={styles.topicSlug}>{topic.slug}</span>
                    </div>
                    <Show when={topic.parent_ids && topic.parent_ids.length > 0}>
                      <div class={styles.parentPath}>
                        Путь: {getTopicPath(topic.id)}
                      </div>
                    </Show>
                  </label>
                </div>
              )}
            </For>
          </div>

          <Show when={getAvailableParents().length === 0 && searchQuery()}>
            <div class={styles.noResults}>
              Нет тем, соответствующих поисковому запросу "{searchQuery()}"
            </div>
          </Show>
        </div>

        <div class={styles.modalActions}>
          <Button variant="secondary" onClick={props.onClose}>
            Отмена
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={selectedParentId() === getCurrentParentId()}
          >
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default TopicParentModal
