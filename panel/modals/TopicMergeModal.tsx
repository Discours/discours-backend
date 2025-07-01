import { Component, createSignal, For, Show } from 'solid-js'
import { MERGE_TOPICS_MUTATION } from '../graphql/mutations'
import styles from '../styles/Form.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

// Типы для топиков
interface Topic {
  id: number
  title: string
  slug: string
  community: number
  stat?: {
    shouts: number
    followers: number
    authors: number
    comments: number
  }
}

interface TopicMergeModalProps {
  isOpen: boolean
  onClose: () => void
  topics: Topic[]
  onSuccess: (message: string) => void
  onError: (error: string) => void
}

interface MergeStats {
  followers_moved: number
  publications_moved: number
  drafts_moved: number
  source_topics_deleted: number
}

const TopicMergeModal: Component<TopicMergeModalProps> = (props) => {
  const [targetTopicId, setTargetTopicId] = createSignal<number | null>(null)
  const [sourceTopicIds, setSourceTopicIds] = createSignal<number[]>([])
  const [preserveTarget, setPreserveTarget] = createSignal(true)
  const [loading, setLoading] = createSignal(false)
  const [error, setError] = createSignal('')

  /**
   * Получает токен авторизации из localStorage или cookie
   */
  const getAuthTokenFromCookie = () => {
    return (
      document.cookie
        .split('; ')
        .find((row) => row.startsWith('auth_token='))
        ?.split('=')[1] || ''
    )
  }

  /**
   * Обработчик выбора/снятия выбора исходной темы
   */
  const handleSourceTopicToggle = (topicId: number, checked: boolean) => {
    if (checked) {
      setSourceTopicIds((prev) => [...prev, topicId])
    } else {
      setSourceTopicIds((prev) => prev.filter((id) => id !== topicId))
    }
  }

  /**
   * Проверяет можно ли выполнить слияние
   */
  const canMerge = () => {
    const target = targetTopicId()
    const sources = sourceTopicIds()

    if (!target || sources.length === 0) {
      return false
    }

    // Проверяем что целевая тема не выбрана как исходная
    if (sources.includes(target)) {
      return false
    }

    // Проверяем что все темы принадлежат одному сообществу
    const targetTopic = props.topics.find((t) => t.id === target)
    if (!targetTopic) return false

    const targetCommunity = targetTopic.community
    const sourcesTopics = props.topics.filter((t) => sources.includes(t.id))

    return sourcesTopics.every((topic) => topic.community === targetCommunity)
  }

  /**
   * Получает название сообщества по ID (заглушка)
   */
  const getCommunityName = (communityId: number) => {
    // Здесь можно добавить запрос к API или кеш сообществ
    return `Сообщество ${communityId}`
  }

  /**
   * Выполняет слияние топиков
   */
  const handleMerge = async () => {
    if (!canMerge()) {
      setError('Невозможно выполнить слияние с текущими настройками')
      return
    }

    setLoading(true)
    setError('')

    try {
      const authToken = localStorage.getItem('auth_token') || getAuthTokenFromCookie()

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authToken ? `Bearer ${authToken}` : ''
        },
        body: JSON.stringify({
          query: MERGE_TOPICS_MUTATION,
          variables: {
            merge_input: {
              target_topic_id: targetTopicId(),
              source_topic_ids: sourceTopicIds(),
              preserve_target_properties: preserveTarget()
            }
          }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const mergeResult = result.data.merge_topics

      if (mergeResult.error) {
        throw new Error(mergeResult.error)
      }

      const stats = mergeResult.stats as MergeStats
      const statsText = stats
        ? ` (перенесено ${stats.followers_moved} подписчиков, ${stats.publications_moved} публикаций, ${stats.drafts_moved} черновиков, удалено ${stats.source_topics_deleted} тем)`
        : ''

      props.onSuccess(mergeResult.message + statsText)
      handleClose()
    } catch (error) {
      const errorMessage = (error as Error).message
      setError(errorMessage)
      props.onError(`Ошибка слияния тем: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Закрывает модалку и сбрасывает состояние
   */
  const handleClose = () => {
    setTargetTopicId(null)
    setSourceTopicIds([])
    setPreserveTarget(true)
    setError('')
    setLoading(false)
    props.onClose()
  }

  /**
   * Получает отфильтрованный список топиков (исключая выбранные как исходные)
   */
  const getAvailableTargetTopics = () => {
    const sources = sourceTopicIds()
    return props.topics.filter((topic) => !sources.includes(topic.id))
  }

  /**
   * Получает отфильтрованный список топиков (исключая целевую тему)
   */
  const getAvailableSourceTopics = () => {
    const target = targetTopicId()
    return props.topics.filter((topic) => topic.id !== target)
  }

  return (
    <Modal isOpen={props.isOpen} onClose={handleClose} title="Слияние тем" size="large">
      <div class={styles.form}>
        <div class={styles.section}>
          <h3 class={styles.sectionTitle}>Выбор целевой темы</h3>
          <p class={styles.description}>
            Выберите тему, в которую будут слиты остальные темы. Все подписчики и публикации будут
            перенесены в эту тему.
          </p>

          <select
            value={targetTopicId() || ''}
            onChange={(e) => setTargetTopicId(e.target.value ? Number.parseInt(e.target.value) : null)}
            class={styles.select}
            disabled={loading()}
          >
            <option value="">Выберите целевую тему</option>
            <For each={getAvailableTargetTopics()}>
              {(topic) => (
                <option value={topic.id}>
                  {topic.title} ({getCommunityName(topic.community)})
                  {topic.stat ? ` - ${topic.stat.shouts} публ., ${topic.stat.followers} подп.` : ''}
                </option>
              )}
            </For>
          </select>
        </div>

        <div class={styles.section}>
          <h3 class={styles.sectionTitle}>Выбор исходных тем для слияния</h3>
          <p class={styles.description}>
            Выберите темы, которые будут слиты в целевую тему. Эти темы будут удалены после переноса всех
            связей.
          </p>

          <Show when={getAvailableSourceTopics().length > 0}>
            <div class={styles.checkboxList}>
              <For each={getAvailableSourceTopics()}>
                {(topic) => {
                  const isChecked = () => sourceTopicIds().includes(topic.id)

                  return (
                    <label class={styles.checkboxItem}>
                      <input
                        type="checkbox"
                        checked={isChecked()}
                        onChange={(e) => handleSourceTopicToggle(topic.id, e.target.checked)}
                        disabled={loading()}
                        class={styles.checkbox}
                      />
                      <div class={styles.checkboxContent}>
                        <div class={styles.topicTitle}>{topic.title}</div>
                        <div class={styles.topicInfo}>
                          {getCommunityName(topic.community)} • ID: {topic.id}
                          {topic.stat && (
                            <span>
                              {' '}
                              • {topic.stat.shouts} публ., {topic.stat.followers} подп.
                            </span>
                          )}
                        </div>
                      </div>
                    </label>
                  )
                }}
              </For>
            </div>
          </Show>
        </div>

        <div class={styles.section}>
          <h3 class={styles.sectionTitle}>Настройки слияния</h3>

          <label class={styles.checkboxItem}>
            <input
              type="checkbox"
              checked={preserveTarget()}
              onChange={(e) => setPreserveTarget(e.target.checked)}
              disabled={loading()}
              class={styles.checkbox}
            />
            <div class={styles.checkboxContent}>
              <div class={styles.optionTitle}>Сохранить свойства целевой темы</div>
              <div class={styles.optionDescription}>
                Если отключено, будут объединены parent_ids из всех тем
              </div>
            </div>
          </label>
        </div>

        <Show when={error()}>
          <div class={styles.error}>{error()}</div>
        </Show>

        <Show when={targetTopicId() && sourceTopicIds().length > 0}>
          <div class={styles.summary}>
            <h4>Предпросмотр слияния:</h4>
            <ul>
              <li>
                <strong>Целевая тема:</strong> {props.topics.find((t) => t.id === targetTopicId())?.title}
              </li>
              <li>
                <strong>Исходные темы:</strong> {sourceTopicIds().length} шт.
                <ul>
                  <For each={sourceTopicIds()}>
                    {(id) => {
                      const topic = props.topics.find((t) => t.id === id)
                      return topic ? <li>{topic.title}</li> : null
                    }}
                  </For>
                </ul>
              </li>
              <li>
                <strong>Действие:</strong> Все подписчики, публикации и черновики будут перенесены в целевую
                тему, исходные темы будут удалены
              </li>
            </ul>
          </div>
        </Show>

        <div class={styles.modalActions}>
          <Button variant="secondary" onClick={handleClose} disabled={loading()}>
            Отмена
          </Button>
          <Button variant="danger" onClick={handleMerge} disabled={!canMerge() || loading()}>
            {loading() ? 'Выполняется слияние...' : 'Слить темы'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default TopicMergeModal
