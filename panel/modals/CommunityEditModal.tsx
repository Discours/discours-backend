import { Component, createEffect, createSignal } from 'solid-js'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/Modal.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

interface Community {
  id: number
  slug: string
  name: string
  desc?: string
  pic: string
  created_at: number
  created_by: {
    id: number
    name: string
    email: string
  }
  stat: {
    shouts: number
    followers: number
    authors: number
  }
}

interface CommunityEditModalProps {
  isOpen: boolean
  community: Community | null // null для создания нового
  onClose: () => void
  onSave: (community: Partial<Community>) => void
}

/**
 * Модальное окно для создания и редактирования сообществ
 */
const CommunityEditModal: Component<CommunityEditModalProps> = (props) => {
  const [formData, setFormData] = createSignal({
    slug: '',
    name: '',
    desc: '',
    pic: ''
  })
  const [errors, setErrors] = createSignal<Record<string, string>>({})

  // Синхронизация с props.community
  createEffect(() => {
    if (props.isOpen) {
      if (props.community) {
        // Редактирование существующего сообщества
        setFormData({
          slug: props.community.slug,
          name: props.community.name,
          desc: props.community.desc || '',
          pic: props.community.pic
        })
      } else {
        // Создание нового сообщества
        setFormData({
          slug: '',
          name: '',
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
    if (!data.name.trim()) {
      newErrors.name = 'Название обязательно'
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

    const communityData = { ...formData() }
    props.onSave(communityData)
  }

  const isCreating = () => props.community === null
  const modalTitle = () =>
    isCreating()
      ? 'Создание нового сообщества'
      : `Редактирование сообщества: ${props.community?.name || ''}`

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title={modalTitle()} size="medium">
      <div class={styles['modal-content']}>
        <div class={formStyles.form}>
          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>
              Slug <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              type="text"
              value={formData().slug}
              onInput={(e) => updateField('slug', e.target.value.toLowerCase())}
              class={`${formStyles.input} ${errors().slug ? formStyles.inputError : ''}`}
              placeholder="уникальный-идентификатор"
              required
            />
            <div class={formStyles.fieldHint}>
              Используется в URL сообщества. Только латинские буквы, цифры, дефисы и подчеркивания.
            </div>
            {errors().slug && <div class={formStyles.fieldError}>{errors().slug}</div>}
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>
              Название <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              type="text"
              value={formData().name}
              onInput={(e) => updateField('name', e.target.value)}
              class={`${formStyles.input} ${errors().name ? formStyles.inputError : ''}`}
              placeholder="Название сообщества"
              required
            />
            {errors().name && <div class={formStyles.fieldError}>{errors().name}</div>}
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>Описание</label>
            <textarea
              value={formData().desc}
              onInput={(e) => updateField('desc', e.target.value)}
              class={formStyles.input}
              style={{
                'min-height': '80px',
                resize: 'vertical'
              }}
              placeholder="Описание сообщества..."
            />
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>Картинка (URL)</label>
            <input
              type="text"
              value={formData().pic}
              onInput={(e) => updateField('pic', e.target.value)}
              class={`${formStyles.input} ${errors().pic ? formStyles.inputError : ''}`}
              placeholder="https://example.com/image.jpg"
            />
            {errors().pic && <div class={formStyles.fieldError}>{errors().pic}</div>}
          </div>

          <div class={styles['modal-actions']}>
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

export default CommunityEditModal
