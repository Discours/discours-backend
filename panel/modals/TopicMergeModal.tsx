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
  body?: string
  community: number
  parent_ids?: number[]
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

interface ValidationErrors {
  target?: string
  sources?: string
  general?: string
}

const TopicMergeModal: Component<TopicMergeModalProps> = (props) => {
  const [targetTopicId, setTargetTopicId] = createSignal<number | null>(null)
  const [sourceTopicIds, setSourceTopicIds] = createSignal<number[]>([])
  const [preserveTarget, setPreserveTarget] = createSignal(true)
  const [loading, setLoading] = createSignal(false)
  const [errors, setErrors] = createSignal<ValidationErrors>({})
  const [searchQuery, setSearchQuery] = createSignal('')

  /**
   * Получает токен авторизации из localStorage или cookie
   */
  const getAuthToken = () => {
    return (
      localStorage.getItem('auth_token') ||
      document.cookie
        .split('; ')
        .find((row) => row.startsWith('auth_token='))
        ?.split('=')[1] ||
      ''
    )
  }

  /**
   * Валидация данных для слияния
   */
  const validateMergeData = (): ValidationErrors => {
    const newErrors: ValidationErrors = {}

    const target = targetTopicId()
    const sources = sourceTopicIds()

    if (!target) {
      newErrors.target = 'Необходимо выбрать целевую тему'
    }

    if (sources.length === 0) {
      newErrors.sources = 'Необходимо выбрать хотя бы одну исходную тему'
    } else if (sources.length > 10) {
      newErrors.sources = 'Нельзя объединять более 10 тем за раз'
    }

    // Проверяем что целевая тема не выбрана как исходная
    if (target && sources.includes(target)) {
      newErrors.general = 'Целевая тема не может быть в списке исходных тем'
    }

    // Проверяем что все темы принадлежат одному сообществу
    if (target && sources.length > 0) {
      const targetTopic = props.topics.find((t) => t.id === target)
      const sourcesTopics = props.topics.filter((t) => sources.includes(t.id))

      if (targetTopic) {
        const targetCommunity = targetTopic.community
        const invalidSources = sourcesTopics.filter((topic) => topic.community !== targetCommunity)

        if (invalidSources.length > 0) {
          newErrors.general = `Все темы должны принадлежать одному сообществу. Темы ${invalidSources.map((t) => `"${t.title}"`).join(', ')} принадлежат другому сообществу`
        }
      }
    }

    return newErrors
  }

  /**
   * Получает название сообщества по ID
   */
  const getCommunityName = (communityId: number): string => {
    // Заглушка - можно добавить запрос к API или кеш сообществ
    return `Сообщество ${communityId}`
  }

  /**
   * Получить отфильтрованный список топиков для поиска
   */
  const getFilteredTopics = (topicsList: Topic[]) => {
    const query = searchQuery().toLowerCase().trim()
    if (!query) return topicsList

    return topicsList.filter(
      (topic) => topic.title?.toLowerCase().includes(query) || topic.slug?.toLowerCase().includes(query)
    )
  }

  /**
   * Обработчик выбора целевой темы
   */
  const handleTargetTopicChange = (e: Event) => {
    const target = e.target as HTMLSelectElement
    const topicId = target.value ? Number.parseInt(target.value) : null
    setTargetTopicId(topicId)

    // Убираем выбранную целевую тему из исходных тем
    if (topicId) {
      setSourceTopicIds((prev) => prev.filter((id) => id !== topicId))
    }

    // Перевалидация
    const newErrors = validateMergeData()
    setErrors(newErrors)
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

    // Перевалидация
    const newErrors = validateMergeData()
    setErrors(newErrors)
  }

  /**
   * Проверяет можно ли выполнить слияние
   */
  const canMerge = () => {
    const validationErrors = validateMergeData()
    return Object.keys(validationErrors).length === 0
  }

  /**
   * Получить статистику для предварительного просмотра
   */
  const getMergePreview = () => {
    const target = targetTopicId()
    const sources = sourceTopicIds()

    if (!target || sources.length === 0) return null

    const targetTopic = props.topics.find((t) => t.id === target)
    const sourceTopics = props.topics.filter((t) => sources.includes(t.id))

    const totalShouts = sourceTopics.reduce((sum, topic) => sum + (topic.stat?.shouts || 0), 0)
    const totalFollowers = sourceTopics.reduce((sum, topic) => sum + (topic.stat?.followers || 0), 0)
    const totalAuthors = sourceTopics.reduce((sum, topic) => sum + (topic.stat?.authors || 0), 0)

    return {
      targetTopic,
      sourceTopics,
      totalShouts,
      totalFollowers,
      totalAuthors,
      sourcesCount: sources.length
    }
  }

  /**
   * Выполняет слияние топиков
   */
  const handleMerge = async () => {
    if (!canMerge()) {
      const validationErrors = validateMergeData()
      setErrors(validationErrors)
      return
    }

    setLoading(true)
    setErrors({})

    try {
      const authToken = getAuthToken()

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
      setErrors({ general: errorMessage })
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
    setErrors({})
    setLoading(false)
    setSearchQuery('')
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

  const preview = getMergePreview()

  return (
    <Modal isOpen={props.isOpen} onClose={handleClose} title="Слияние тем" size="large">
      <div class={styles.form}>
        {/* Общие ошибки */}
        <Show when={errors().general}>
          <div class={styles.formError}>{errors().general}</div>
        </Show>

        {/* Выбор целевой темы */}
        <div class={styles.section}>
          <h3 class={styles.sectionTitle}>🎯 Целевая тема</h3>
          <p class={styles.sectionDescription}>
            Выберите тему, в которую будут слиты остальные темы. Все подписчики и публикации будут
            перенесены в эту тему, а исходные темы будут удалены.
          </p>

          <div class={styles.field}>
            <label class={styles.label}>
              Целевая тема:
              <select
                class={`${styles.select} ${errors().target ? styles.inputError : ''}`}
                value={targetTopicId() || ''}
                onChange={handleTargetTopicChange}
                required
              >
                <option value="">Выберите целевую тему...</option>
                <For each={getFilteredTopics(getAvailableTargetTopics())}>
                  {(topic) => (
                    <option value={topic.id}>
                      {topic.title} ({topic.slug}){topic.stat ? ` • ${topic.stat.shouts} публикаций` : ''}
                    </option>
                  )}
                </For>
              </select>
              <Show when={errors().target}>
                <div class={styles.errorMessage}>{errors().target}</div>
              </Show>
            </label>
          </div>
        </div>

        {/* Поиск и выбор исходных тем */}
        <div class={styles.section}>
          <h3 class={styles.sectionTitle}>📥 Исходные темы</h3>
          <p class={styles.sectionDescription}>
            Выберите темы, которые будут слиты в целевую тему. Все их данные будут перенесены, а сами темы
            будут удалены.
          </p>

          <div class={styles.field}>
            <label class={styles.label}>
              Поиск тем:
              <input
                type="text"
                class={styles.input}
                value={searchQuery()}
                onInput={(e) => setSearchQuery(e.currentTarget.value)}
                placeholder="Введите название или slug для поиска..."
              />
            </label>
          </div>

          <Show when={errors().sources}>
            <div class={styles.errorMessage}>{errors().sources}</div>
          </Show>

          <div class={styles.availableParents}>
            <div class={styles.sectionHeader}>
              <strong>Доступные темы для слияния:</strong>
              <span class={styles.hint}>Выбрано: {sourceTopicIds().length}</span>
            </div>

            <div class={styles.parentsGrid}>
              <For each={getFilteredTopics(getAvailableSourceTopics())}>
                {(topic) => {
                  const isChecked = () => sourceTopicIds().includes(topic.id)
                  const isDisabled = () =>
                    targetTopicId() &&
                    topic.community !== props.topics.find((t) => t.id === targetTopicId())?.community

                  return (
                    <label
                      class={`${styles.parentCheckbox} ${isDisabled() ? styles.disabled : ''}`}
                      title={isDisabled() ? 'Тема принадлежит другому сообществу' : ''}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked()}
                        disabled={isDisabled() || false}
                        onChange={(e) => handleSourceTopicToggle(topic.id, e.currentTarget.checked)}
                      />
                      <div class={styles.parentLabel}>
                        <div class={styles.parentTitle}>{topic.title}</div>
                        <div class={styles.parentSlug}>{topic.slug}</div>
                        <div class={styles.parentStats}>
                          {getCommunityName(topic.community)}
                          {topic.stat && (
                            <>
                              <span> • {topic.stat.shouts} публикаций</span>
                              <span> • {topic.stat.followers} подписчиков</span>
                            </>
                          )}
                        </div>
                      </div>
                    </label>
                  )
                }}
              </For>
            </div>

            <Show when={getFilteredTopics(getAvailableSourceTopics()).length === 0}>
              <div class={styles.noParents}>
                <Show when={searchQuery()}>Не найдено тем по запросу "{searchQuery()}"</Show>
                <Show when={!searchQuery()}>Нет доступных тем для слияния</Show>
              </div>
            </Show>
          </div>
        </div>

        {/* Предварительный просмотр слияния */}
        <Show when={preview}>
          <div class={styles.section}>
            <h3 class={styles.sectionTitle}>📊 Предварительный просмотр</h3>

            <div class={styles.hierarchyPath}>
              <div>
                <strong>Целевая тема:</strong> {preview!.targetTopic!.title}
              </div>
              <div class={styles.pathDisplay}>
                <span>Слияние {preview!.sourcesCount} тем:</span>
                <For each={preview!.sourceTopics}>
                  {(topic) => <span class={styles.pathItem}>{topic.title}</span>}
                </For>
              </div>

              <div style="margin-top: 1rem;">
                <strong>Ожидаемые результаты:</strong>
                <ul style="margin: 0.5rem 0; padding-left: 1.5rem;">
                  <li>Будет перенесено ~{preview!.totalShouts} публикаций</li>
                  <li>Будет перенесено ~{preview!.totalFollowers} подписчиков</li>
                  <li>Будет объединено ~{preview!.totalAuthors} авторов</li>
                  <li>Будет удалено {preview!.sourcesCount} исходных тем</li>
                </ul>
              </div>
            </div>
          </div>
        </Show>

        {/* Настройки слияния */}
        <div class={styles.section}>
          <h3 class={styles.sectionTitle}>⚙️ Настройки слияния</h3>

          <div class={styles.field}>
            <label class={styles.parentCheckbox}>
              <input
                type="checkbox"
                checked={preserveTarget()}
                onChange={(e) => setPreserveTarget(e.currentTarget.checked)}
              />
              <div class={styles.parentLabel}>
                <div class={styles.parentTitle}>Сохранить свойства целевой темы</div>
                <div class={styles.parentStats}>
                  Если включено, описание и другие свойства целевой темы не будут изменены. Если выключено,
                  свойства могут быть объединены с исходными темами.
                </div>
              </div>
            </label>
          </div>
        </div>

        {/* Кнопки */}
        <div class={styles.actions}>
          <Button type="button" variant="secondary" onClick={handleClose} disabled={loading()}>
            Отмена
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleMerge}
            disabled={!canMerge() || loading()}
            loading={loading()}
          >
            {loading() ? 'Выполняется слияние...' : `Слить ${sourceTopicIds().length} тем`}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default TopicMergeModal
