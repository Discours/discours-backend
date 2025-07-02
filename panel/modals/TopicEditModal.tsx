import { createEffect, createSignal, For, Show } from 'solid-js'
import { Topic, useData } from '../context/data'
import styles from '../styles/Form.module.css'
import modalStyles from '../styles/Modal.module.css'
import EditableCodePreview from '../ui/EditableCodePreview'
import Modal from '../ui/Modal'

interface TopicEditModalProps {
  topic: Topic
  isOpen: boolean
  onClose: () => void
  onSave: (updatedTopic: Topic) => void
  onError?: (message: string) => void
}

export default function TopicEditModal(props: TopicEditModalProps) {
  const { communities, topics, getCommunityName, selectedCommunity } = useData()

  // Состояние формы
  const [formData, setFormData] = createSignal({
    id: 0,
    title: '',
    slug: '',
    body: '',
    community: 0,
    parent_ids: [] as number[]
  })

  // Состояние для выбора родителей
  const [availableParents, setAvailableParents] = createSignal<Topic[]>([])
  const [parentSearch, setParentSearch] = createSignal('')

  // Состояние для редактирования body
  const [showBodyEditor, setShowBodyEditor] = createSignal(false)
  const [bodyContent, setBodyContent] = createSignal('')

  const [saving, setSaving] = createSignal(false)

  // Инициализация формы при открытии
  createEffect(() => {
    if (props.isOpen && props.topic) {
      console.log('[TopicEditModal] Initializing with topic:', props.topic)
      setFormData({
        id: props.topic.id,
        title: props.topic.title || '',
        slug: props.topic.slug || '',
        body: props.topic.body || '',
        community: selectedCommunity() || 0,
        parent_ids: props.topic.parent_ids || []
      })
      setBodyContent(props.topic.body || '')
      updateAvailableParents(selectedCommunity() || 0)
    }
  })

  // Обновление доступных родителей при смене сообщества
  const updateAvailableParents = (communityId: number) => {
    const allTopics = topics()
    const currentTopicId = formData().id

    // Фильтруем топики того же сообщества, исключая текущий топик
    const filteredTopics = allTopics.filter(
      (topic) => topic.community === communityId && topic.id !== currentTopicId
    )

    setAvailableParents(filteredTopics)
  }

  // Фильтрация родителей по поиску
  const filteredParents = () => {
    const search = parentSearch().toLowerCase()
    if (!search) return availableParents()

    return availableParents().filter(
      (topic) => topic.title?.toLowerCase().includes(search) || topic.slug?.toLowerCase().includes(search)
    )
  }

  // Обработка изменения сообщества
  const handleCommunityChange = (e: Event) => {
    const target = e.target as HTMLSelectElement
    const communityId = Number.parseInt(target.value)

    setFormData((prev) => ({
      ...prev,
      community: communityId,
      parent_ids: [] // Сбрасываем родителей при смене сообщества
    }))

    updateAvailableParents(communityId)
  }

  // Обработка изменения родителей
  const handleParentToggle = (parentId: number) => {
    setFormData((prev) => ({
      ...prev,
      parent_ids: prev.parent_ids.includes(parentId)
        ? prev.parent_ids.filter((id) => id !== parentId)
        : [...prev.parent_ids, parentId]
    }))
  }

  // Обработка изменения полей формы
  const handleFieldChange = (field: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value
    }))
  }

  // Открытие редактора body
  const handleOpenBodyEditor = () => {
    setBodyContent(formData().body)
    setShowBodyEditor(true)
  }

  // Сохранение body из редактора
  const handleBodySave = (content: string) => {
    setFormData((prev) => ({
      ...prev,
      body: content
    }))
    setBodyContent(content)
    setShowBodyEditor(false)
  }

  // Получение пути до корня для топика
  const getTopicPath = (topicId: number): string => {
    const topic = topics().find((t) => t.id === topicId)
    if (!topic) return 'Неизвестный топик'

    const community = getCommunityName(topic.community)
    return `${community} → ${topic.title}`
  }

  // Сохранение изменений
  const handleSave = async () => {
    try {
      setSaving(true)

      const updatedTopic = {
        ...props.topic,
        ...formData()
      }

      console.log('[TopicEditModal] Saving topic:', updatedTopic)

      // TODO: Здесь должен быть вызов API для сохранения
      // await updateTopic(updatedTopic)

      props.onSave(updatedTopic)
      props.onClose()
    } catch (error) {
      console.error('[TopicEditModal] Error saving topic:', error)
      props.onError?.(error instanceof Error ? error.message : 'Ошибка сохранения топика')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Modal
        isOpen={props.isOpen && !showBodyEditor()}
        onClose={props.onClose}
        title="Редактирование топика"
        size="large"
      >
        <div class={styles.form}>
          {/* Основная информация */}
          <div class={styles.section}>
            <h3>Основная информация</h3>

            <div class={styles.field}>
              <label class={styles.label}>
                Название:
                <input
                  type="text"
                  class={styles.input}
                  value={formData().title}
                  onInput={(e) => handleFieldChange('title', e.currentTarget.value)}
                  placeholder="Введите название топика..."
                />
              </label>
            </div>

            <div class={styles.field}>
              <label class={styles.label}>
                Slug:
                <input
                  type="text"
                  class={styles.input}
                  value={formData().slug}
                  onInput={(e) => handleFieldChange('slug', e.currentTarget.value)}
                  placeholder="Введите slug топика..."
                />
              </label>
            </div>

            <div class={styles.field}>
              <label class={styles.label}>
                Сообщество:
                <select class={styles.select} value={formData().community} onChange={handleCommunityChange}>
                  <option value={0}>Выберите сообщество</option>
                  <For each={communities()}>
                    {(community) => <option value={community.id}>{community.name}</option>}
                  </For>
                </select>
              </label>
            </div>
          </div>

          {/* Содержимое */}
          <div class={styles.section}>
            <h3>Содержимое</h3>

            <div class={styles.field}>
              <label class={styles.label}>Body:</label>
              <div class={styles.bodyPreview} onClick={handleOpenBodyEditor}>
                <Show when={formData().body}>
                  <div class={styles.bodyContent}>
                    {formData().body.length > 200
                      ? `${formData().body.substring(0, 200)}...`
                      : formData().body}
                  </div>
                </Show>
                <Show when={!formData().body}>
                  <div class={styles.bodyPlaceholder}>Нет содержимого. Нажмите для редактирования.</div>
                </Show>
                <div class={styles.bodyHint}>✏️ Кликните для редактирования в полноэкранном редакторе</div>
              </div>
            </div>
          </div>

          {/* Родительские топики */}
          <Show when={formData().community > 0}>
            <div class={styles.section}>
              <h3>Родительские топики</h3>

              <div class={styles.field}>
                <label class={styles.label}>
                  Поиск родителей:
                  <input
                    type="text"
                    class={styles.input}
                    value={parentSearch()}
                    onInput={(e) => setParentSearch(e.currentTarget.value)}
                    placeholder="Введите название для поиска..."
                  />
                </label>
              </div>

              <Show when={formData().parent_ids.length > 0}>
                <div class={styles.selectedParents}>
                  <strong>Выбранные родители:</strong>
                  <ul class={styles.parentsList}>
                    <For each={formData().parent_ids}>
                      {(parentId) => (
                        <li class={styles.parentItem}>
                          <span>{getTopicPath(parentId)}</span>
                          <button
                            type="button"
                            class={styles.removeButton}
                            onClick={() => handleParentToggle(parentId)}
                          >
                            ✕
                          </button>
                        </li>
                      )}
                    </For>
                  </ul>
                </div>
              </Show>

              <div class={styles.availableParents}>
                <strong>Доступные родители:</strong>
                <div class={styles.parentsGrid}>
                  <For each={filteredParents()}>
                    {(parent) => (
                      <label class={styles.parentCheckbox}>
                        <input
                          type="checkbox"
                          checked={formData().parent_ids.includes(parent.id)}
                          onChange={() => handleParentToggle(parent.id)}
                        />
                        <span class={styles.parentLabel}>
                          <strong>{parent.title}</strong>
                          <br />
                          <small>{parent.slug}</small>
                        </span>
                      </label>
                    )}
                  </For>
                </div>

                <Show when={filteredParents().length === 0}>
                  <div class={styles.noParents}>
                    <Show when={parentSearch()}>Не найдено топиков по запросу "{parentSearch()}"</Show>
                    <Show when={!parentSearch()}>Нет доступных родительских топиков в этом сообществе</Show>
                  </div>
                </Show>
              </div>
            </div>
          </Show>

          {/* Кнопки */}
          <div class={modalStyles.modalActions}>
            <button
              type="button"
              class={`${styles.button} ${styles.buttonSecondary}`}
              onClick={props.onClose}
              disabled={saving()}
            >
              Отмена
            </button>
            <button
              type="button"
              class={`${styles.button} ${styles.buttonPrimary}`}
              onClick={handleSave}
              disabled={saving() || !formData().title || !formData().slug || formData().community === 0}
            >
              {saving() ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Редактор body */}
      <Modal
        isOpen={showBodyEditor()}
        onClose={() => setShowBodyEditor(false)}
        title="Редактирование содержимого топика"
        size="large"
      >
        <EditableCodePreview
          content={bodyContent()}
          maxHeight="85vh"
          onContentChange={setBodyContent}
          onSave={handleBodySave}
          onCancel={() => setShowBodyEditor(false)}
          placeholder="Введите содержимое топика..."
        />
      </Modal>
    </>
  )
}
