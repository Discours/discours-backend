import { Component, createEffect, createSignal } from 'solid-js'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/Modal.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

interface Collection {
  id: number
  slug: string
  title: string
  desc?: string
  pic?: string
  amount?: number
  published_at?: number
  created_at: number
  created_by: {
    id: number
    name: string
    email: string
  }
}

interface CollectionEditModalProps {
  isOpen: boolean
  collection: Collection | null // null для создания новой
  onClose: () => void
  onSave: (collection: Partial<Collection>) => void
}

/**
 * Модальное окно для создания и редактирования коллекций
 */
const CollectionEditModal: Component<CollectionEditModalProps> = (props) => {
  const [formData, setFormData] = createSignal({
    slug: '',
    title: '',
    desc: '',
    pic: ''
  })
  const [errors, setErrors] = createSignal<Record<string, string>>({})

  // Синхронизация с props.collection
  createEffect(() => {
    if (props.isOpen) {
      if (props.collection) {
        // Редактирование существующей коллекции
        setFormData({
          slug: props.collection.slug,
          title: props.collection.title,
          desc: props.collection.desc || '',
          pic: props.collection.pic || ''
        })
      } else {
        // Создание новой коллекции
        setFormData({
          slug: '',
          title: '',
          desc: '',
          pic: ''
        })
      }
      setErrors({})
    }
  })

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    const data = formData()

    // Валидация slug
    if (!data.slug.trim()) {
      newErrors.slug = 'Slug обязателен'
    } else if (!/^[a-z0-9-_]+$/.test(data.slug)) {
      newErrors.slug = 'Slug может содержать только латинские буквы, цифры, дефисы и подчеркивания'
    }

    // Валидация названия
    if (!data.title.trim()) {
      newErrors.title = 'Название обязательно'
    }

    // Валидация URL картинки (если указан)
    if (data.pic.trim() && !/^https?:\/\/.+/.test(data.pic)) {
      newErrors.pic = 'Некорректный URL картинки'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    // Очищаем ошибку для поля при изменении
    setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const handleSave = () => {
    if (!validateForm()) {
      return
    }

    const collectionData = { ...formData() }
    props.onSave(collectionData)
  }

  const isCreating = () => props.collection === null
  const modalTitle = () =>
    isCreating() ? 'Создание новой коллекции' : `Редактирование коллекции: ${props.collection?.title || ''}`

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title={modalTitle()} size="medium">
      <div class={styles.modalContent}>
        <div class={formStyles.form}>
          <div class={formStyles.fieldGroup}>
            <label class={formStyles.label}>
              <span class={formStyles.labelText}>
                <span class={formStyles.labelIcon}>📝</span>
                Название
                <span class={formStyles.required}>*</span>
              </span>
            </label>
            <input
              type="text"
              class={`${formStyles.input} ${errors().title ? formStyles.error : ''}`}
              value={formData().title}
              onInput={(e) => updateField('title', e.target.value)}
              placeholder="Введите название коллекции"
              required
            />
            {errors().title && (
              <div class={formStyles.fieldError}>
                <span class={formStyles.errorIcon}>⚠️</span>
                {errors().title}
              </div>
            )}
          </div>

          <div class={formStyles.fieldGroup}>
            <label class={formStyles.label}>
              <span class={formStyles.labelText}>
                <span class={formStyles.labelIcon}>🔗</span>
                Slug
                <span class={formStyles.required}>*</span>
              </span>
            </label>
            <input
              type="text"
              class={`${formStyles.input} ${errors().slug ? formStyles.error : ''}`}
              value={formData().slug}
              onInput={(e) => updateField('slug', e.target.value)}
              placeholder="collection-slug"
              required
            />
            {errors().slug && (
              <div class={formStyles.fieldError}>
                <span class={formStyles.errorIcon}>⚠️</span>
                {errors().slug}
              </div>
            )}
          </div>

          <div class={formStyles.fieldGroup}>
            <label class={formStyles.label}>
              <span class={formStyles.labelText}>
                <span class={formStyles.labelIcon}>📄</span>
                Описание
              </span>
            </label>
            <textarea
              class={formStyles.textarea}
              value={formData().desc}
              onInput={(e) => updateField('desc', e.target.value)}
              placeholder="Описание коллекции (необязательно)"
              rows="4"
            />
          </div>

          <div class={formStyles.fieldGroup}>
            <label class={formStyles.label}>
              <span class={formStyles.labelText}>
                <span class={formStyles.labelIcon}>🖼️</span>
                URL картинки
              </span>
            </label>
            <input
              type="url"
              class={`${formStyles.input} ${errors().pic ? formStyles.error : ''}`}
              value={formData().pic}
              onInput={(e) => updateField('pic', e.target.value)}
              placeholder="https://example.com/image.jpg"
            />
            {errors().pic && (
              <div class={formStyles.fieldError}>
                <span class={formStyles.errorIcon}>⚠️</span>
                {errors().pic}
              </div>
            )}
            <div class={formStyles.hint}>
              <span class={formStyles.hintIcon}>💡</span>
              Необязательно. URL изображения для обложки коллекции.
            </div>
          </div>

          <div class={styles.modalActions}>
            <Button variant="secondary" onClick={props.onClose}>
              Отмена
            </Button>
            <Button variant="primary" onClick={handleSave}>
              {isCreating() ? 'Создать' : 'Сохранить'}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}

export default CollectionEditModal
