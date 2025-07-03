import { createEffect, createSignal, For, Show, on } from 'solid-js'
import { Topic, useData } from '../context/data'
import { query } from '../graphql'
import { ADMIN_UPDATE_TOPIC_MUTATION } from '../graphql/mutations'
import styles from '../styles/Form.module.css'
import Modal from '../ui/Modal'
import TopicPillsCloud, { type TopicPill } from '../ui/TopicPillsCloud'
import HTMLEditor from '../ui/HTMLEditor'

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

  const [saving, setSaving] = createSignal(false)

  // Инициализация формы при открытии
  createEffect(() => {
    if (props.isOpen && props.topic) {
      const topicCommunity = props.topic.community || selectedCommunity() || 0
      setFormData({
        id: props.topic.id,
        title: props.topic.title || '',
        slug: props.topic.slug || '',
        body: props.topic.body || '',
        community: topicCommunity,
        parent_ids: props.topic.parent_ids || []
      })
      updateAvailableParents(topicCommunity, props.topic.id)
    }
  })

  // Обновление доступных родителей при изменении сообщества в форме
  createEffect(on(() => formData().community, (communityId) => {
    if (communityId > 0) {
      updateAvailableParents(communityId)
    }
  }))

  // Обновление доступных родителей при смене сообщества
  const updateAvailableParents = (communityId: number, excludeTopicId?: number) => {
    const allTopics = topics()
    const currentTopicId = excludeTopicId || formData().id

    // Фильтруем топики того же сообщества, исключая текущий топик
    const filteredTopics = allTopics.filter(
      (topic) => topic.community === communityId && topic.id !== currentTopicId
    )

    setAvailableParents(filteredTopics)
  }

  /**
   * Преобразование Topic в TopicPill для компонента TopicPillsCloud
   */
  const convertTopicsToTopicPills = (topics: Topic[]): TopicPill[] => {
    return topics.map(topic => ({
      id: topic.id.toString(),
      title: topic.title || '',
      slug: topic.slug || '',
      community: getCommunityName(topic.community),
      parent_ids: (topic.parent_ids || []).map(id => id.toString()),
    }))
  }

  /**
   * Обработка изменения выбора родительских топиков из таблеточек
   */
  const handleParentSelectionChange = (selectedIds: string[]) => {
    const parentIds = selectedIds.map(id => Number.parseInt(id))
    setFormData((prev) => ({
      ...prev,
      parent_ids: parentIds
    }))
  }

  // Сообщество топика изменить нельзя, поэтому обработчик не нужен

  // Обработка изменения полей формы
  const handleFieldChange = (field: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value
    }))
  }

  // Сохранение изменений
  const handleSave = async () => {
    try {
      setSaving(true)

      const topicData = formData()

      // Вызываем админскую мутацию для сохранения
      const result = await query<{
        adminUpdateTopic: {
          success: boolean
          error?: string
          topic?: Topic
        }
      }>(`${location.origin}/graphql`, ADMIN_UPDATE_TOPIC_MUTATION, {
        topic: {
          id: topicData.id,
          title: topicData.title,
          slug: topicData.slug,
          body: topicData.body,
          community: topicData.community,
          parent_ids: topicData.parent_ids
        }
      })

      if (result.adminUpdateTopic.success && result.adminUpdateTopic.topic) {
        console.log('[TopicEditModal] Topic saved successfully:', result.adminUpdateTopic.topic)
        props.onSave(result.adminUpdateTopic.topic)
        props.onClose()
      } else {
        const errorMessage = result.adminUpdateTopic.error || 'Неизвестная ошибка'
        throw new Error(errorMessage)
      }
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
        isOpen={props.isOpen}
        onClose={props.onClose}
        title="Редактирование топика"
        size="large"
        footer={
          <>
            <button
              type="button"
              class={`${styles.button} ${styles.secondary}`}
              onClick={props.onClose}
              disabled={saving()}
            >
              Отмена
            </button>
            <button
              type="button"
              class={`${styles.button} ${styles.primary}`}
              onClick={handleSave}
              disabled={saving() || !formData().title || !formData().slug || formData().community === 0}
            >
              {saving() ? 'Сохранение...' : 'Сохранить'}
            </button>
          </>
        }
      >
        <div class={styles.form}>
          {/* Основная информация */}
          <div class={styles.section}>
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
                <div class={`${styles.input} ${styles.disabled} ${styles.communityDisplay}`}>
                  {getCommunityName(formData().community) || 'Сообщество не выбрано'}
                </div>
              </label>
              <div class={`${styles.hint} ${styles.warningHint}`}>
                📍 Сообщество топика нельзя изменить после создания
              </div>
            </div>
          </div>

          {/* Содержимое */}
          <div class={styles.section}>
            <div class={styles.field}>
              <label class={styles.label}>
                Описание:
                <HTMLEditor
                  value={formData().body}
                  onInput={(value) => handleFieldChange('body', value)}
                />
              </label>
            </div>
          </div>

          {/* Родительские топики */}
          <Show when={formData().community > 0}>
            <div class={styles.section}>
              {/* Компонент с таблеточками для выбора родителей */}
              <div class={styles.field}>
                <TopicPillsCloud
                    topics={convertTopicsToTopicPills(availableParents())}
                    selectedTopics={formData().parent_ids.map(id => id.toString())}
                    onSelectionChange={handleParentSelectionChange}
                    excludeTopics={[formData().id.toString()]}
                    showSearch={true}
                    searchPlaceholder="Задайте родительские темы..."
                    hideSelectedInHeader={true}
                  />

              </div>
            </div>
          </Show>

        </div>
      </Modal>
    </>
  )
}
