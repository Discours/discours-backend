import { Component, createEffect, createSignal } from 'solid-js'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/Modal.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

interface Topic {
  id: number
  slug: string
  title: string
  body?: string
  pic?: string
  community: number
  parent_ids?: number[]
}

interface TopicEditModalProps {
  isOpen: boolean
  topic: Topic | null
  onClose: () => void
  onSave: (topic: Topic) => void
}

/**
 * Модальное окно для редактирования топиков
 */
const TopicEditModal: Component<TopicEditModalProps> = (props) => {
  const [formData, setFormData] = createSignal<Topic>({
    id: 0,
    slug: '',
    title: '',
    body: '',
    pic: '',
    community: 0,
    parent_ids: []
  })

  const [parentIdsText, setParentIdsText] = createSignal('')
  let bodyRef: HTMLDivElement | undefined

  // Синхронизация с props.topic
  createEffect(() => {
    if (props.topic) {
      setFormData({ ...props.topic })
      setParentIdsText(props.topic.parent_ids?.join(', ') || '')

      // Устанавливаем содержимое в contenteditable div
      if (bodyRef) {
        bodyRef.innerHTML = props.topic.body || ''
      }
    }
  })

  const handleSave = () => {
    // Парсим parent_ids из строки
    const parentIds = parentIdsText()
      .split(',')
      .map((id) => Number.parseInt(id.trim()))
      .filter((id) => !Number.isNaN(id))

    const updatedTopic = {
      ...formData(),
      parent_ids: parentIds.length > 0 ? parentIds : undefined
    }

    props.onSave(updatedTopic)
  }

  const handleBodyInput = (e: Event) => {
    const target = e.target as HTMLDivElement
    setFormData((prev) => ({ ...prev, body: target.innerHTML }))
  }

  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={`Редактирование топика: ${props.topic?.title || ''}`}
    >
      <div class={styles['modal-content']}>
        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>ID</label>
          <input
            type="text"
            value={formData().id}
            disabled
            class={formStyles.input}
            style={{ background: '#f5f5f5', cursor: 'not-allowed' }}
          />
        </div>

        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>Slug</label>
          <input
            type="text"
            value={formData().slug}
            onInput={(e) => setFormData((prev) => ({ ...prev, slug: e.target.value }))}
            class={formStyles.input}
            required
          />
        </div>

        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>Название</label>
          <input
            type="text"
            value={formData().title}
            onInput={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
            class={formStyles.input}
          />
        </div>

        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>Описание (HTML)</label>
          <div
            ref={bodyRef}
            contentEditable
            onInput={handleBodyInput}
            class={formStyles.input}
            style={{
              'min-height': '120px',
              'font-family': 'Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
              'font-size': '13px',
              'line-height': '1.4',
              'white-space': 'pre-wrap',
              'overflow-wrap': 'break-word'
            }}
            data-placeholder="Введите HTML описание топика..."
          />
        </div>

        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>Картинка (URL)</label>
          <input
            type="text"
            value={formData().pic || ''}
            onInput={(e) => setFormData((prev) => ({ ...prev, pic: e.target.value }))}
            class={formStyles.input}
            placeholder="https://example.com/image.jpg"
          />
        </div>

        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>Сообщество (ID)</label>
          <input
            type="number"
            value={formData().community}
            onInput={(e) =>
              setFormData((prev) => ({ ...prev, community: Number.parseInt(e.target.value) || 0 }))
            }
            class={formStyles.input}
            min="0"
          />
        </div>

        <div class={formStyles['form-group']}>
          <label class={formStyles.label}>
            Родительские топики (ID через запятую)
            <small style={{ display: 'block', color: '#666', 'margin-top': '4px' }}>
              Например: 1, 5, 12
            </small>
          </label>
          <input
            type="text"
            value={parentIdsText()}
            onInput={(e) => setParentIdsText(e.target.value)}
            class={formStyles.input}
            placeholder="1, 5, 12"
          />
        </div>

        <div class={styles['modal-actions']}>
          <Button variant="secondary" onClick={props.onClose}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleSave}>
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default TopicEditModal
