import { Component, createSignal, For, Show } from 'solid-js'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import styles from '../styles/Form.module.css'
import { SET_TOPIC_PARENT_MUTATION } from '../graphql/mutations'

// Типы для топиков
interface Topic {
  id: number
  title: string
  slug: string
  parent_ids?: number[]
  community: number
}

interface TopicSimpleParentModalProps {
  isOpen: boolean
  onClose: () => void
  topic: Topic | null
  allTopics: Topic[]
  onSuccess: (message: string) => void
  onError: (error: string) => void
}

const TopicSimpleParentModal: Component<TopicSimpleParentModalProps> = (props) => {
  const [selectedParentId, setSelectedParentId] = createSignal<number | null>(null)
  const [loading, setLoading] = createSignal(false)
  const [searchQuery, setSearchQuery] = createSignal('')

  /**
   * Получает токен авторизации
   */
  const getAuthTokenFromCookie = () => {
    return document.cookie
      .split('; ')
      .find(row => row.startsWith('auth_token='))
      ?.split('=')[1] || ''
  }

  /**
   * Получает текущего родителя темы
   */
  const getCurrentParentId = (): number | null => {
    if (!props.topic?.parent_ids || props.topic.parent_ids.length === 0) {
      return null
    }
    return props.topic.parent_ids[props.topic.parent_ids.length - 1]
  }

  /**
   * Получает путь темы до корня
   */
  const getTopicPath = (topicId: number): string => {
    const topic = props.allTopics.find(t => t.id === topicId)
    if (!topic) return 'Неизвестная тема'

    if (!topic.parent_ids || topic.parent_ids.length === 0) {
      return topic.title
    }

    const parentPath = getTopicPath(topic.parent_ids[topic.parent_ids.length - 1])
    return `${parentPath} → ${topic.title}`
  }

  /**
   * Проверяет циклические зависимости
   */
  const isDescendant = (parentId: number, childId: number): boolean => {
    if (parentId === childId) return true

    const checkDescendants = (currentId: number): boolean => {
      const descendants = props.allTopics.filter(t =>
        t.parent_ids && t.parent_ids.includes(currentId)
      )

      for (const descendant of descendants) {
        if (descendant.id === childId || checkDescendants(descendant.id)) {
          return true
        }
      }
      return false
    }

    return checkDescendants(parentId)
  }

  /**
   * Получает доступных родителей (исключая потомков и темы из других сообществ)
   */
  const getAvailableParents = () => {
    if (!props.topic) return []

    const query = searchQuery().toLowerCase()

    return props.allTopics.filter(topic => {
      // Исключаем саму тему
      if (topic.id === props.topic!.id) return false

      // Только темы из того же сообщества
      if (topic.community !== props.topic!.community) return false

      // Исключаем потомков (предотвращаем циклы)
      if (isDescendant(topic.id, props.topic!.id)) return false

      // Фильтр по поиску
      if (query && !topic.title.toLowerCase().includes(query)) return false

      return true
    })
  }

  /**
   * Выполняет назначение родителя
   */
  const handleSetParent = async () => {
    if (!props.topic) return

    setLoading(true)

    try {
      const authToken = localStorage.getItem('auth_token') || getAuthTokenFromCookie()

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authToken ? `Bearer ${authToken}` : ''
        },
        body: JSON.stringify({
          query: SET_TOPIC_PARENT_MUTATION,
          variables: {
            topic_id: props.topic.id,
            parent_id: selectedParentId()
          }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const setResult = result.data.set_topic_parent

      if (setResult.error) {
        throw new Error(setResult.error)
      }

      props.onSuccess(setResult.message)
      handleClose()

    } catch (error) {
      const errorMessage = (error as Error).message
      props.onError(`Ошибка назначения родителя: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Закрывает модалку и сбрасывает состояние
   */
  const handleClose = () => {
    setSelectedParentId(null)
    setSearchQuery('')
    setLoading(false)
    props.onClose()
  }

  return (
    <Modal
      isOpen={props.isOpen}
      onClose={handleClose}
      title="Назначить родительскую тему"
      size="medium"
    >
      <div class={styles.parentSelectorContainer}>
        <Show when={props.topic}>
          <div class={styles.currentSelection}>
            <h4>Редактируемая тема:</h4>
            <div class={styles.topicDisplay}>
              <strong>{props.topic?.title}</strong> #{props.topic?.id}
            </div>

            <div class={styles.currentParent}>
              <strong>Текущее расположение:</strong>
              <div class={styles.parentPath}>
                {getCurrentParentId() ?
                  getTopicPath(props.topic!.id) :
                  <span class={styles.noParent}>🏠 Корневая тема</span>
                }
              </div>
            </div>
          </div>

          <div class={styles.searchSection}>
            <label class={styles.label}>Поиск новой родительской темы:</label>
            <input
              type="text"
              value={searchQuery()}
              onInput={(e) => setSearchQuery(e.target.value)}
              placeholder="Введите название темы..."
              class={styles.searchInput}
              disabled={loading()}
            />
          </div>

          <div class={styles.parentOptions}>
            <h4>Выберите новую родительскую тему:</h4>

            {/* Опция корневой темы */}
            <div class={styles.parentsList}>
              <label class={styles.parentOption}>
                <input
                  type="radio"
                  name="parentSelection"
                  checked={selectedParentId() === null}
                  onChange={() => setSelectedParentId(null)}
                  disabled={loading()}
                />
                <div class={styles.parentOptionLabel}>
                  <div class={styles.topicTitle}>
                    🏠 Сделать корневой темой
                  </div>
                  <div class={styles.parentDescription}>
                    Тема будет перемещена на верхний уровень иерархии
                  </div>
                </div>
              </label>
            </div>

            {/* Список доступных родителей */}
            <div class={styles.parentsList}>
              <Show when={getAvailableParents().length > 0}>
                <For each={getAvailableParents()}>
                  {(topic) => (
                    <label class={styles.parentOption}>
                      <input
                        type="radio"
                        name="parentSelection"
                        checked={selectedParentId() === topic.id}
                        onChange={() => setSelectedParentId(topic.id)}
                        disabled={loading()}
                      />
                      <div class={styles.parentOptionLabel}>
                        <div class={styles.topicTitle}>
                          {topic.title}
                        </div>
                        <div class={styles.parentDescription}>
                          <span class={styles.topicId}>ID: {topic.id}</span>
                          <span class={styles.topicSlug}>• {topic.slug}</span>
                          <br />
                          <strong>Путь:</strong> {getTopicPath(topic.id)}
                        </div>
                      </div>
                    </label>
                  )}
                </For>
              </Show>

              <Show when={getAvailableParents().length === 0}>
                <div class={styles.noResults}>
                  {searchQuery() ?
                    'Не найдено подходящих тем по запросу' :
                    'Нет доступных родительских тем'
                  }
                </div>
              </Show>
            </div>
          </div>

          <Show when={selectedParentId() !== null}>
            <div class={styles.preview}>
              <h4>Предварительный просмотр:</h4>
              <div class={styles.previewPath}>
                <strong>Новое расположение:</strong><br />
                {getTopicPath(selectedParentId()!)} → <strong>{props.topic?.title}</strong>
              </div>
            </div>
          </Show>

          <div class={styles.modalActions}>
            <Button
              variant="secondary"
              onClick={handleClose}
              disabled={loading()}
            >
              Отмена
            </Button>
            <Button
              variant="primary"
              onClick={handleSetParent}
              disabled={loading() || (selectedParentId() === getCurrentParentId())}
            >
              {loading() ? 'Назначение...' : 'Назначить родителя'}
            </Button>
          </div>
        </Show>
      </div>
    </Modal>
  )
}

export default TopicSimpleParentModal
