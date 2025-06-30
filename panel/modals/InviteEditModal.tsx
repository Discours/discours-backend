import { Component, createEffect, createSignal } from 'solid-js'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/Modal.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

interface Author {
  id: number
  name: string
  email: string
  slug: string
}

interface Shout {
  id: number
  title: string
  slug: string
  created_by: Author
}

interface Invite {
  inviter_id: number
  author_id: number
  shout_id: number
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
  inviter: Author
  author: Author
  shout: Shout
  created_at?: number
}

interface InviteEditModalProps {
  isOpen: boolean
  invite: Invite | null // null для создания нового
  onClose: () => void
  onSave: (invite: Partial<Invite>) => void
}

/**
 * Модальное окно для создания и редактирования приглашений
 */
const InviteEditModal: Component<InviteEditModalProps> = (props) => {
  const [formData, setFormData] = createSignal({
    inviter_id: 0,
    author_id: 0,
    shout_id: 0,
    status: 'PENDING' as 'PENDING' | 'ACCEPTED' | 'REJECTED'
  })
  const [errors, setErrors] = createSignal<Record<string, string>>({})

  // Синхронизация с props.invite
  createEffect(() => {
    if (props.isOpen) {
      if (props.invite) {
        // Редактирование существующего приглашения
        setFormData({
          inviter_id: props.invite.inviter_id,
          author_id: props.invite.author_id,
          shout_id: props.invite.shout_id,
          status: props.invite.status
        })
      } else {
        // Создание нового приглашения
        setFormData({
          inviter_id: 0,
          author_id: 0,
          shout_id: 0,
          status: 'PENDING'
        })
      }
      setErrors({})
    }
  })

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    const data = formData()

    // Валидация ID приглашающего
    if (!data.inviter_id || data.inviter_id <= 0) {
      newErrors.inviter_id = 'ID приглашающего обязателен'
    }

    // Валидация ID приглашаемого
    if (!data.author_id || data.author_id <= 0) {
      newErrors.author_id = 'ID приглашаемого обязателен'
    }

    // Валидация ID публикации
    if (!data.shout_id || data.shout_id <= 0) {
      newErrors.shout_id = 'ID публикации обязателен'
    }

    // Проверка что приглашающий и приглашаемый не совпадают
    if (data.inviter_id === data.author_id && data.inviter_id > 0) {
      newErrors.author_id = 'Приглашающий и приглашаемый не могут быть одним и тем же автором'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const updateField = (field: string, value: string | number) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    // Очищаем ошибку для поля при изменении
    setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const handleSave = () => {
    if (!validateForm()) {
      return
    }

    const inviteData = { ...formData() }
    props.onSave(inviteData)
  }

  const isCreating = () => props.invite === null
  const modalTitle = () =>
    isCreating()
      ? 'Создание нового приглашения'
      : `Редактирование приглашения: ${props.invite?.inviter.name || ''} → ${props.invite?.author.name || ''}`

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title={modalTitle()} size="medium">
      <div class={styles['modal-content']}>
        <div class={formStyles.form}>
          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>
              ID приглашающего <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              type="number"
              value={formData().inviter_id}
              onInput={(e) => updateField('inviter_id', parseInt(e.target.value) || 0)}
              class={`${formStyles.input} ${errors().inviter_id ? formStyles.inputError : ''}`}
              placeholder="1"
              required
              disabled={!isCreating()} // При редактировании ID нельзя менять
            />
            <div class={formStyles.fieldHint}>
              ID автора, который отправляет приглашение
            </div>
            {errors().inviter_id && <div class={formStyles.fieldError}>{errors().inviter_id}</div>}
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>
              ID приглашаемого <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              type="number"
              value={formData().author_id}
              onInput={(e) => updateField('author_id', parseInt(e.target.value) || 0)}
              class={`${formStyles.input} ${errors().author_id ? formStyles.inputError : ''}`}
              placeholder="2"
              required
              disabled={!isCreating()} // При редактировании ID нельзя менять
            />
            <div class={formStyles.fieldHint}>
              ID автора, которого приглашают к сотрудничеству
            </div>
            {errors().author_id && <div class={formStyles.fieldError}>{errors().author_id}</div>}
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>
              ID публикации <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              type="number"
              value={formData().shout_id}
              onInput={(e) => updateField('shout_id', parseInt(e.target.value) || 0)}
              class={`${formStyles.input} ${errors().shout_id ? formStyles.inputError : ''}`}
              placeholder="123"
              required
              disabled={!isCreating()} // При редактировании ID нельзя менять
            />
            <div class={formStyles.fieldHint}>
              ID публикации, к которой приглашают на сотрудничество
            </div>
            {errors().shout_id && <div class={formStyles.fieldError}>{errors().shout_id}</div>}
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles.label}>
              Статус <span style={{ color: 'red' }}>*</span>
            </label>
            <select
              value={formData().status}
              onChange={(e) => updateField('status', e.target.value)}
              class={formStyles.input}
              required
            >
              <option value="PENDING">Ожидает ответа</option>
              <option value="ACCEPTED">Принято</option>
              <option value="REJECTED">Отклонено</option>
            </select>
            <div class={formStyles.fieldHint}>
              Текущий статус приглашения
            </div>
          </div>

          {/* Информация о связанных объектах при редактировании */}
          {!isCreating() && props.invite && (
            <div class={formStyles['form-group']}>
              <label class={formStyles.label}>Информация о приглашении</label>
              <div class={formStyles.fieldHint} style={{ 'margin-bottom': '8px' }}>
                <strong>Приглашающий:</strong> {props.invite.inviter.name} ({props.invite.inviter.email})
              </div>
              <div class={formStyles.fieldHint} style={{ 'margin-bottom': '8px' }}>
                <strong>Приглашаемый:</strong> {props.invite.author.name} ({props.invite.author.email})
              </div>
              <div class={formStyles.fieldHint}>
                <strong>Публикация:</strong> {props.invite.shout.title}
              </div>
            </div>
          )}

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

export default InviteEditModal
