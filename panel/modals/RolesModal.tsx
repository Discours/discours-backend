import { Component, createEffect, createSignal, For } from 'solid-js'
import type { AdminUserInfo } from '../graphql/generated/schema'
import formStyles from '../styles/Form.module.css'
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

// Доступные роли в системе
const AVAILABLE_ROLES = [
  {
    id: 'Администратор',
    name: 'Системный администратор',
    description: 'Администраторы определяются автоматически по настройкам сервера',
    emoji: '🪄'
  },
  {
    id: 'Редактор',
    name: 'Редактор',
    description: 'Редактирование публикаций и управление сообществом',
    emoji: '✒️'
  },
  {
    id: 'Эксперт',
    name: 'Эксперт',
    description: 'Добавление доказательств и опровержений, управление темами',
    emoji: '🔬'
  },
  {
    id: 'Автор',
    name: 'Автор',
    description: 'Создание и редактирование своих публикаций',
    emoji: '📝'
  },
  {
    id: 'Читатель',
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
    roles: props.user.roles || [] // Включаем все роли, включая администратора
  })

  const [errors, setErrors] = createSignal<Record<string, string>>({})
  const [loading, setLoading] = createSignal(false)

  // Проверяем, является ли пользователь администратором по ролям, которые приходят с сервера
  const isAdmin = () => {
    return (props.user.roles || []).includes('Администратор')
  }

  // Получаем информацию о роли по ID
  const getRoleInfo = (roleId: string) => {
    return AVAILABLE_ROLES.find((role) => role.id === roleId) || { name: roleId, emoji: '👤' }
  }

  // Формируем строку с ролями и эмоджи
  const getRolesDisplay = () => {
    const roles = formData().roles
    if (roles.length === 0) {
      return isAdmin() ? '🪄 Администратор' : 'Роли не назначены'
    }

    const roleTexts = roles.map((roleId) => {
      const role = getRoleInfo(roleId)
      return `${role.emoji} ${role.name}`
    })

    if (isAdmin()) {
      return `🪄 Администратор, ${roleTexts.join(', ')}`
    }

    return roleTexts.join(', ')
  }

  // Обновляем форму при изменении пользователя
  createEffect(() => {
    if (props.user) {
      setFormData({
        id: props.user.id,
        email: props.user.email || '',
        name: props.user.name || '',
        slug: props.user.slug || '',
        roles: props.user.roles || [] // Включаем все роли, включая администратора
      })
      setErrors({})
    }
  })

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    // Очищаем ошибку при изменении поля
    if (errors()[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }))
    }
  }

  const handleRoleToggle = (roleId: string) => {
    // Роль администратора нельзя изменить вручную
    if (roleId === 'Администратор') {
      return
    }

    setFormData((prev) => {
      const currentRoles = prev.roles
      const newRoles = currentRoles.includes(roleId)
        ? currentRoles.filter((r) => r !== roleId)
        : [...currentRoles, roleId]
      return { ...prev, roles: newRoles }
    })

    // Очищаем ошибку ролей при изменении
    if (errors().roles) {
      setErrors((prev) => ({ ...prev, roles: '' }))
    }
  }

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}
    const data = formData()

    // Email
    if (!data.email.trim()) {
      newErrors.email = 'Email обязателен'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim())) {
      newErrors.email = 'Неверный формат email'
    }

    // Имя
    if (!data.name.trim()) {
      newErrors.name = 'Имя обязательно'
    } else if (data.name.trim().length < 2) {
      newErrors.name = 'Имя должно содержать минимум 2 символа'
    }

    // Slug
    if (!data.slug.trim()) {
      newErrors.slug = 'Slug обязателен'
    } else if (!/^[a-z0-9_-]+$/.test(data.slug.trim())) {
      newErrors.slug = 'Slug может содержать только латинские буквы, цифры, дефисы и подчеркивания'
    }

    // Роли (админы освобождаются от этого требования)
    if (!isAdmin() && data.roles.filter((role) => role !== 'Администратор').length === 0) {
      newErrors.roles = 'Выберите хотя бы одну роль (или назначьте админский email)'
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
      // Отправляем только обычные роли, админская роль определяется на сервере по email
      await props.onSave(formData())
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
      size="large"
    >
      <div class={formStyles.form}>
        {/* Компактная системная информация */}
        <div class={formStyles.fieldGroup}>
          <div
            style={{
              display: 'grid',
              'grid-template-columns': 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
              padding: '1rem',
              background: 'var(--form-bg-light)',
              'font-size': '0.875rem',
              color: 'var(--form-text-light)'
            }}
          >
            <div>
              <strong>ID:</strong> {props.user.id}
            </div>
            <div>
              <strong>Регистрация:</strong>{' '}
              {props.user.created_at
                ? new Date(props.user.created_at * 1000).toLocaleDateString('ru-RU')
                : '—'}
            </div>
            <div>
              <strong>Активность:</strong>{' '}
              {props.user.last_seen
                ? new Date(props.user.last_seen * 1000).toLocaleDateString('ru-RU')
                : '—'}
            </div>
          </div>
        </div>

        {/* Текущие роли в строку */}
        <div class={formStyles.fieldGroup} style={{ display: 'none' }}>
          <label class={formStyles.label}>
            <span class={formStyles.labelText}>
              <span class={formStyles.labelIcon}>👤</span>
              Текущие роли
            </span>
          </label>
          <div
            style={{
              padding: '0.875rem 1rem',
              background: isAdmin() ? 'rgba(245, 158, 11, 0.1)' : 'var(--form-bg-light)',
              border: isAdmin() ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid var(--form-divider)',
              'font-size': '0.95rem',
              'font-weight': '500',
              color: isAdmin() ? '#d97706' : 'var(--form-text)'
            }}
          >
            {getRolesDisplay()}
          </div>
        </div>

        {/* Основные данные в компактной сетке */}
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
            <div class={formStyles.hint}>
              <span class={formStyles.hintIcon}>💡</span>
              Администраторы определяются автоматически по настройкам сервера
            </div>
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
            <div class={formStyles.hint}>
              <span class={formStyles.hintIcon}>💡</span>
              Только латинские буквы, цифры, дефисы и подчеркивания
            </div>
            {errors().slug && (
              <div class={formStyles.fieldError}>
                <span class={formStyles.errorIcon}>⚠️</span>
                {errors().slug}
              </div>
            )}
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
                const isAdminRole = role.id === 'Администратор'
                const isSelected = formData().roles.includes(role.id)
                const isDisabled = isAdminRole // Роль администратора всегда заблокирована

                return (
                  <label
                    class={`${formStyles.roleCard} ${isSelected ? formStyles.roleCardSelected : ''} ${isDisabled ? formStyles.roleCardDisabled || '' : ''}`}
                    style={{
                      opacity: isDisabled ? 0.7 : 1,
                      cursor: isDisabled ? 'not-allowed' : 'pointer',
                      background: isAdminRole && isSelected ? 'rgba(245, 158, 11, 0.1)' : undefined,
                      border: isAdminRole && isSelected ? '1px solid rgba(245, 158, 11, 0.3)' : undefined
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleRoleToggle(role.id)}
                      disabled={loading() || isDisabled}
                      style={{ display: 'none' }}
                    />
                    <div class={formStyles.roleHeader}>
                      <span class={formStyles.roleName}>
                        <span style={{ 'margin-right': '0.5rem', 'font-size': '1.1rem' }}>
                          {role.emoji}
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
        <div
          style={{
            display: 'flex',
            gap: '0.75rem',
            'justify-content': 'flex-end',
            'margin-top': '1.5rem',
            'padding-top': '1rem',
            'border-top': '1px solid var(--form-divider)'
          }}
        >
          <Button variant="secondary" onClick={props.onClose} disabled={loading()}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleSave} loading={loading()}>
            Сохранить
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default UserEditModal
