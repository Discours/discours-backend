import { Component, createEffect, createSignal, For } from 'solid-js'
import type { AdminUserInfo } from '../graphql/generated/schema'
import styles from '../styles/Form.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

export interface UserEditModalProps {
  user: AdminUserInfo
  isOpen: boolean
  onClose: () => void
  onSave: (userData: {
    id: number
    email?: string
    name?: string
    slug?: string
    roles: string[]
  }) => Promise<void>
}

const AVAILABLE_ROLES = [
  { id: 'admin', name: 'Администратор', description: 'Полный доступ к системе' },
  { id: 'editor', name: 'Редактор', description: 'Редактирование публикаций и управление сообществом' },
  {
    id: 'expert',
    name: 'Эксперт',
    description: 'Добавление доказательств и опровержений, управление темами'
  },
  { id: 'author', name: 'Автор', description: 'Создание и редактирование своих публикаций' },
  { id: 'reader', name: 'Читатель', description: 'Чтение и комментирование' }
]

const UserEditModal: Component<UserEditModalProps> = (props) => {
  const [formData, setFormData] = createSignal({
    email: props.user.email || '',
    name: props.user.name || '',
    slug: props.user.slug || '',
    roles: props.user.roles || []
  })
  const [loading, setLoading] = createSignal(false)
  const [errors, setErrors] = createSignal<Record<string, string>>({})

  // Сброс формы при открытии модалки
  createEffect(() => {
    if (props.isOpen) {
      setFormData({
        email: props.user.email || '',
        name: props.user.name || '',
        slug: props.user.slug || '',
        roles: props.user.roles || []
      })
      setErrors({})
    }
  })

  const validateForm = () => {
    const newErrors: Record<string, string> = {}
    const data = formData()

    // Валидация email
    if (!data.email.trim()) {
      newErrors.email = 'Email обязателен'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
      newErrors.email = 'Некорректный формат email'
    }

    // Валидация имени
    if (!data.name.trim()) {
      newErrors.name = 'Имя обязательно'
    }

    // Валидация slug
    if (!data.slug.trim()) {
      newErrors.slug = 'Slug обязателен'
    } else if (!/^[a-z0-9-_]+$/.test(data.slug)) {
      newErrors.slug = 'Slug может содержать только латинские буквы, цифры, дефисы и подчеркивания'
    }

    // Валидация ролей
    if (data.roles.length === 0) {
      newErrors.roles = 'Выберите хотя бы одну роль'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    // Очищаем ошибку для поля при изменении
    setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const handleRoleToggle = (roleId: string) => {
    const current = formData().roles
    const newRoles = current.includes(roleId) ? current.filter((r) => r !== roleId) : [...current, roleId]

    setFormData((prev) => ({ ...prev, roles: newRoles }))
    setErrors((prev) => ({ ...prev, roles: '' }))
  }

  const handleSave = async () => {
    if (!validateForm()) {
      return
    }

    setLoading(true)
    try {
      await props.onSave({
        id: props.user.id,
        email: formData().email,
        name: formData().name,
        slug: formData().slug,
        roles: formData().roles
      })
      props.onClose()
    } catch (error) {
      console.error('Error saving user:', error)
      setErrors({ general: 'Ошибка при сохранении данных пользователя' })
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (timestamp?: number | null) => {
    if (!timestamp) return '—'
    return new Date(timestamp * 1000).toLocaleString('ru-RU')
  }

  const footer = (
    <>
      <Button variant="secondary" onClick={props.onClose} disabled={loading()}>
        Отмена
      </Button>
      <Button variant="primary" onClick={handleSave} loading={loading()} disabled={loading()}>
        Сохранить изменения
      </Button>
    </>
  )

  return (
    <Modal
      title={`Редактирование пользователя #${props.user.id}`}
      isOpen={props.isOpen}
      onClose={props.onClose}
      footer={footer}
      size="medium"
    >
      <div class={styles.form}>
        {errors().general && (
          <div class={styles.error} style={{ 'margin-bottom': '20px' }}>
            {errors().general}
          </div>
        )}

        {/* Информационная секция */}
        <div
          class={styles.section}
          style={{
            'margin-bottom': '20px',
            padding: '15px',
            background: '#f8f9fa',
            'border-radius': '8px'
          }}
        >
          <h4 style={{ margin: '0 0 10px 0', color: '#495057' }}>Системная информация</h4>
          <div style={{ 'font-size': '14px', color: '#6c757d' }}>
            <div>
              <strong>ID:</strong> {props.user.id}
            </div>
            <div>
              <strong>Дата регистрации:</strong> {formatDate(props.user.created_at)}
            </div>
            <div>
              <strong>Последняя активность:</strong> {formatDate(props.user.last_seen)}
            </div>
          </div>
        </div>

        {/* Основные данные */}
        <div class={styles.section}>
          <h4 style={{ margin: '0 0 15px 0', color: '#495057' }}>Основные данные</h4>

          <div class={styles.field}>
            <label for="email" class={styles.label}>
              Email <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              id="email"
              type="email"
              class={`${styles.input} ${errors().email ? styles.inputError : ''}`}
              value={formData().email}
              onInput={(e) => updateField('email', e.currentTarget.value)}
              disabled={loading()}
              placeholder="user@example.com"
            />
            {errors().email && <div class={styles.fieldError}>{errors().email}</div>}
          </div>

          <div class={styles.field}>
            <label for="name" class={styles.label}>
              Имя <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              id="name"
              type="text"
              class={`${styles.input} ${errors().name ? styles.inputError : ''}`}
              value={formData().name}
              onInput={(e) => updateField('name', e.currentTarget.value)}
              disabled={loading()}
              placeholder="Иван Иванов"
            />
            {errors().name && <div class={styles.fieldError}>{errors().name}</div>}
          </div>

          <div class={styles.field}>
            <label for="slug" class={styles.label}>
              Slug (URL) <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              id="slug"
              type="text"
              class={`${styles.input} ${errors().slug ? styles.inputError : ''}`}
              value={formData().slug}
              onInput={(e) => updateField('slug', e.currentTarget.value.toLowerCase())}
              disabled={loading()}
              placeholder="ivan-ivanov"
            />
            <div class={styles.fieldHint}>
              Используется в URL профиля. Только латинские буквы, цифры, дефисы и подчеркивания.
            </div>
            {errors().slug && <div class={styles.fieldError}>{errors().slug}</div>}
          </div>
        </div>

        {/* Роли */}
        <div class={styles.section}>
          <h4 style={{ margin: '0 0 15px 0', color: '#495057' }}>
            Роли <span style={{ color: 'red' }}>*</span>
          </h4>

          <div class={styles.rolesGrid}>
            <For each={AVAILABLE_ROLES}>
              {(role) => (
                <label
                  class={`${styles.roleCard} ${formData().roles.includes(role.id) ? styles.roleCardSelected : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={formData().roles.includes(role.id)}
                    onChange={() => handleRoleToggle(role.id)}
                    disabled={loading()}
                    style={{ display: 'none' }}
                  />
                  <div class={styles.roleHeader}>
                    <span class={styles.roleName}>{role.name}</span>
                    <span class={styles.roleCheckmark}>
                      {formData().roles.includes(role.id) ? '✓' : ''}
                    </span>
                  </div>
                  <div class={styles.roleDescription}>{role.description}</div>
                </label>
              )}
            </For>
          </div>
          {errors().roles && <div class={styles.fieldError}>{errors().roles}</div>}
        </div>
      </div>
    </Modal>
  )
}

export default UserEditModal
