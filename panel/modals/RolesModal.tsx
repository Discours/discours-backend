import { Component, createEffect, createSignal, For, Show } from 'solid-js'
import type { AdminUserInfo } from '../graphql/generated/schema'
import formStyles from '../styles/Form.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

// Список администраторских email
const ADMIN_EMAILS = ['welcome@discours.io']

export interface UserEditModalProps {
  user: AdminUserInfo
  isOpen: boolean
  onClose: () => void
  onSave: (userData: {
    id: number
    email?: string
    name?: string
    slug?: string
    roles: string
  }) => Promise<void>
}

// Список доступных ролей с сохранением идентификаторов
const AVAILABLE_ROLES = [
  {
    id: 'admin',
    name: 'Системный администратор',
    description: 'Администраторы определяются автоматически по настройкам сервера',
    emoji: '🪄'
  },
  {
    id: 'editor',
    name: 'Редактор',
    description: 'Редактирование публикаций и управление сообществом',
    emoji: '✒️'
  },
  {
    id: 'expert',
    name: 'Эксперт',
    description: 'Добавление доказательств и опровержений, управление темами',
    emoji: '🔬'
  },
  {
    id: 'author',
    name: 'Автор',
    description: 'Создание и редактирование своих публикаций',
    emoji: '📝'
  },
  {
    id: 'reader',
    name: 'Читатель',
    description: 'Чтение и комментирование',
    emoji: '📖'
  }
]

// Создаем маппинги для конвертации между ID и названиями
const ROLE_ID_TO_NAME = Object.fromEntries(AVAILABLE_ROLES.map((role) => [role.id, role.name]))

const ROLE_NAME_TO_ID = Object.fromEntries(AVAILABLE_ROLES.map((role) => [role.name, role.id]))

const UserEditModal: Component<UserEditModalProps> = (props) => {
  // Инициализируем форму с использованием ID ролей
  const [formData, setFormData] = createSignal({
    id: props.user.id,
    email: props.user.email || '',
    name: props.user.name || '',
    slug: props.user.slug || '',
    roles: (props.user.roles || []).map((roleName) => ROLE_NAME_TO_ID[roleName] || roleName)
  })

  const [errors, setErrors] = createSignal<Record<string, string>>({})
  const [loading, setLoading] = createSignal(false)

  // Проверяем, является ли пользователь администратором по ролям, которые приходят с сервера
  const isAdmin = () => {
    const roles = formData().roles
    return roles.includes('admin') || (props.user.email ? ADMIN_EMAILS.includes(props.user.email) : false)
  }

  // Обновляем поле формы
  const updateField = (field: keyof ReturnType<typeof formData>, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    if (errors()[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  // Обновляем эффект для инициализации формы
  createEffect(() => {
    if (props.user) {
      setFormData({
        id: props.user.id,
        email: props.user.email || '',
        name: props.user.name || '',
        slug: props.user.slug || '',
        roles: (props.user.roles || []).map((roleName) => ROLE_NAME_TO_ID[roleName] || roleName)
      })
      setErrors({})
    }
  })

  // Обновим логику проверки выбранности роли
  const isRoleSelected = (roleId: string) => {
    const roles = formData().roles || []
    const isSelected = roles.includes(roleId)
    console.log(`Checking role ${roleId}:`, isSelected)
    return isSelected
  }

  const handleRoleToggle = (roleId: string) => {
    console.log('Attempting to toggle role:', roleId)
    console.log('Current roles:', formData().roles)
    console.log('Is admin:', isAdmin())
    console.log('Role is admin:', roleId === 'admin')

    if (roleId === 'admin') {
      console.log('Admin role cannot be changed')
      return // Системная роль не может быть изменена
    }

    // Создаем новый массив ролей с учетом текущего состояния
    setFormData((prev) => {
      const currentRoles = prev.roles || []
      const isCurrentlySelected = currentRoles.includes(roleId)

      const newRoles = isCurrentlySelected
        ? currentRoles.filter((r) => r !== roleId) // Убираем роль
        : [...currentRoles, roleId] // Добавляем роль

      console.log('Current roles before:', currentRoles)
      console.log('Is currently selected:', isCurrentlySelected)
      console.log('New roles:', newRoles)

      return { ...prev, roles: newRoles }
    })

    // Очищаем ошибки, связанные с ролями
    if (errors().roles) {
      setErrors((prev) => {
        const newErrors = { ...prev }
        delete newErrors.roles
        return newErrors
      })
    }
  }

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}
    const data = formData()

    if (!data.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim())) {
      newErrors.email = 'Неверный формат email'
    }

    if (!data.name.trim() || data.name.trim().length < 2) {
      newErrors.name = 'Имя должно содержать минимум 2 символа'
    }

    if (!data.slug.trim() || !/^[a-z0-9_-]+$/.test(data.slug.trim())) {
      newErrors.slug = 'Slug может содержать только латинские буквы, цифры, дефисы и подчеркивания'
    }

    if (!isAdmin() && (data.roles || []).filter((role: string) => role !== 'admin').length === 0) {
      newErrors.roles = 'Выберите хотя бы одну роль'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSave = async () => {
    if (!validateForm()) {
      return
    }

    setLoading(true)
    try {
      await props.onSave({
        ...formData(),
        // Конвертируем ID ролей обратно в названия для сервера
        roles: (formData().roles || []).map((roleId) => ROLE_ID_TO_NAME[roleId]).join(',')
      })
      props.onClose()
    } catch (error) {
      console.error('Ошибка при сохранении пользователя:', error)
      setErrors({ general: 'Ошибка при сохранении пользователя' })
    } finally {
      setLoading(false)
    }
  }

  // Обновляем компонент выбора роли
  const RoleSelector = (props: {
    role: (typeof AVAILABLE_ROLES)[0]
    isSelected: boolean
    onToggle: () => void
    isDisabled?: boolean
  }) => {
    return (
      <label
        class={`${formStyles.roleCard} ${props.isSelected ? formStyles.roleCardSelected : ''} ${props.isDisabled ? formStyles.roleCardDisabled : ''}`}
        style={{
          opacity: props.isDisabled ? 0.7 : 1,
          cursor: props.isDisabled ? 'not-allowed' : 'pointer',
          background: props.role.id === 'admin' && props.isSelected ? 'rgba(245, 158, 11, 0.1)' : undefined,
          border:
            props.role.id === 'admin' && props.isSelected ? '1px solid rgba(245, 158, 11, 0.3)' : undefined
        }}
        onClick={(e) => {
          e.preventDefault()
          if (!props.isDisabled) {
            props.onToggle()
          }
        }}
      >
        <div class={formStyles.roleHeader}>
          <span class={formStyles.roleName}>
            <span style={{ 'margin-right': '0.5rem', 'font-size': '1.1rem' }}>{props.role.emoji}</span>
            {props.role.name}
            <Show when={props.role.id === 'admin'}>
              <span
                style={{
                  'margin-left': '0.5rem',
                  'font-size': '0.75rem',
                  color: '#d97706',
                  'font-weight': 'normal'
                }}
              >
                (системная)
              </span>
            </Show>
          </span>
          <div
            style={{
              width: '20px',
              height: '20px',
              'border-radius': '50%',
              border: `2px solid ${props.isSelected ? '#3b82f6' : '#a1a1aa'}`,
              'background-color': props.isSelected ? '#3b82f6' : 'transparent',
              display: 'flex',
              'align-items': 'center',
              'justify-content': 'center',
              cursor: props.isDisabled ? 'not-allowed' : 'pointer'
            }}
          >
            <Show when={props.isSelected}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                stroke-width="3"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </Show>
          </div>
        </div>
        <div class={formStyles.roleDescription}>{props.role.description}</div>
      </label>
    )
  }

  // В основном компоненте модального окна обновляем рендеринг ролей
  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={`Редактирование пользователя #${props.user.id}`}
    >
      <div class={formStyles.form}>
        {/* Основные данные */}
        <div class={formStyles.fieldGroup}>
          <div
            style={{
              display: 'grid',
              'grid-template-columns': 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '1rem'
            }}
          >
            <div class={formStyles.fieldGroup}>
              <label class={formStyles.label}>
                <span class={formStyles.labelText}>
                  <span class={formStyles.labelIcon}>📧</span>
                  Email
                  <span class={formStyles.required}>*</span>
                </span>
              </label>
              <input
                type="email"
                class={`${formStyles.input} ${errors().email ? formStyles.error : ''}`}
                value={formData().email}
                onInput={(e) => updateField('email', e.currentTarget.value)}
                disabled={loading()}
                placeholder="user@example.com"
              />
              {errors().email && (
                <div class={formStyles.fieldError}>
                  <span class={formStyles.errorIcon}>⚠️</span>
                  {errors().email}
                </div>
              )}
            </div>

            <div class={formStyles.fieldGroup}>
              <label class={formStyles.label}>
                <span class={formStyles.labelText}>
                  <span class={formStyles.labelIcon}>👤</span>
                  Имя
                  <span class={formStyles.required}>*</span>
                </span>
              </label>
              <input
                type="text"
                class={`${formStyles.input} ${errors().name ? formStyles.error : ''}`}
                value={formData().name}
                onInput={(e) => updateField('name', e.currentTarget.value)}
                disabled={loading()}
                placeholder="Иван Иванов"
              />
              {errors().name && (
                <div class={formStyles.fieldError}>
                  <span class={formStyles.errorIcon}>⚠️</span>
                  {errors().name}
                </div>
              )}
            </div>

            <div class={formStyles.fieldGroup}>
              <label class={formStyles.label}>
                <span class={formStyles.labelText}>
                  <span class={formStyles.labelIcon}>🔗</span>
                  Slug (URL)
                  <span class={formStyles.required}>*</span>
                </span>
              </label>
              <input
                type="text"
                class={`${formStyles.input} ${errors().slug ? formStyles.error : ''}`}
                value={formData().slug}
                onInput={(e) => updateField('slug', e.currentTarget.value.toLowerCase())}
                disabled={loading()}
                placeholder="ivan-ivanov"
              />
              {errors().slug && (
                <div class={formStyles.fieldError}>
                  <span class={formStyles.errorIcon}>⚠️</span>
                  {errors().slug}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Роли */}
        <div class={formStyles.fieldGroup}>
          <label class={formStyles.label}>
            <span class={formStyles.labelText}>
              <span class={formStyles.labelIcon}>⚙️</span>
              Управление ролями
              <span class={formStyles.required} style={{ display: isAdmin() ? 'none' : 'inline' }}>
                *
              </span>
            </span>
          </label>

          <div class={formStyles.rolesGrid}>
            <For each={AVAILABLE_ROLES}>
              {(role) => (
                <RoleSelector
                  role={role}
                  isSelected={isRoleSelected(role.id)}
                  onToggle={() => handleRoleToggle(role.id)}
                  isDisabled={role.id === 'admin'}
                />
              )}
            </For>
          </div>

          {!isAdmin() && errors().roles && (
            <div class={formStyles.fieldError}>
              <span class={formStyles.errorIcon}>⚠️</span>
              {errors().roles}
            </div>
          )}

          <div class={formStyles.hint}>
            <span class={formStyles.hintIcon}>💡</span>
            Системные роли (администратор) назначаются автоматически и не могут быть изменены вручную.
            {!isAdmin() &&
              ' Выберите дополнительные роли для пользователя - минимум одна роль обязательна.'}
          </div>
        </div>

        {/* Общая ошибка */}
        {errors().general && (
          <div class={formStyles.fieldError}>
            <span class={formStyles.errorIcon}>⚠️</span>
            {errors().general}
          </div>
        )}

        {/* Компактные кнопки действий */}
        <div class={formStyles.actions}>
          <Button type="button" onClick={props.onClose} disabled={loading()}>
            Отмена
          </Button>
          <Button type="button" onClick={handleSave} disabled={loading()}>
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default UserEditModal
