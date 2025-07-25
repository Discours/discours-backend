import { Component, createEffect, createSignal, For } from 'solid-js'
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

// Доступные роли в системе
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

const UserEditModal: Component<UserEditModalProps> = (props) => {
  const [formData, setFormData] = createSignal({
    id: props.user.id,
    email: props.user.email || '',
    name: props.user.name || '',
    slug: props.user.slug || '',
    roles: props.user.roles || []
  })

  const [errors, setErrors] = createSignal<Record<string, string>>({})
  const [loading, setLoading] = createSignal(false)

  // Проверяем, является ли пользователь администратором по ролям, которые приходят с сервера
  const isAdmin = () => {
    const roles = formData().roles
    return roles.includes('admin') || (props.user.email ? ADMIN_EMAILS.includes(props.user.email) : false)
  }

  // Получаем информацию о роли по ID
  const getRoleInfo = (roleId: string) => {
    return AVAILABLE_ROLES.find((role) => role.id === roleId) || { name: roleId, emoji: '👤' }
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

  // Обновляем форму при изменении пользователя
  createEffect(() => {
    if (props.user) {
      setFormData({
        id: props.user.id,
        email: props.user.email || '',
        name: props.user.name || '',
        slug: props.user.slug || '',
        roles: props.user.roles || []
      })
      setErrors({})
    }
  })

  const handleRoleToggle = (roleId: string) => {
    if (roleId === 'admin') {
      return
    }

    setFormData((prev) => {
      const currentRoles = prev.roles || []
      const newRoles = currentRoles.includes(roleId)
        ? currentRoles.filter((r: string) => r !== roleId)
        : [...currentRoles, roleId]
      return { ...prev, roles: newRoles }
    })

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
        roles: (formData().roles || []).join(',')
      })
      props.onClose()
    } catch (error) {
      console.error('Ошибка при сохранении пользователя:', error)
      setErrors({ general: 'Ошибка при сохранении пользователя' })
    } finally {
      setLoading(false)
    }
  }

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
              {(role) => {
                const isAdminRole = role.id === 'admin'
                const isSelected = (formData().roles || []).includes(role.id)
                const isDisabled = isAdminRole
                const roleInfo = getRoleInfo(role.id)

                return (
                  <label
                    class={`${formStyles.roleCard} ${isSelected ? formStyles.roleCardSelected : ''} ${isDisabled ? formStyles.roleCardDisabled : ''}`}
                    style={{
                      opacity: isDisabled ? 0.7 : 1,
                      cursor: isDisabled ? 'not-allowed' : 'pointer',
                      background: isAdminRole && isSelected ? 'rgba(245, 158, 11, 0.1)' : undefined,
                      border: isAdminRole && isSelected ? '1px solid rgba(245, 158, 11, 0.3)' : undefined
                    }}
                    onClick={() => !isDisabled && handleRoleToggle(role.id)} // Добавляем обработчик клика
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleRoleToggle(role.id)}
                      disabled={loading() || isDisabled}
                      style={{
                        cursor: isDisabled ? 'not-allowed' : 'pointer',
                        margin: '0 0.5rem 0 0'
                      }}
                    />
                    <div class={formStyles.roleHeader}>
                      <span class={formStyles.roleName}>
                        <span style={{ 'margin-right': '0.5rem', 'font-size': '1.1rem' }}>
                          {roleInfo.emoji}
                        </span>
                        {role.name}
                        {isAdminRole && (
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
                        )}
                      </span>
                      <span class={formStyles.roleCheckmark}>{isSelected ? '✓' : ''}</span>
                    </div>
                    <div class={formStyles.roleDescription}>{role.description}</div>
                  </label>
                )
              }}
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
