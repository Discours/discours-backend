import { createSignal, For, onMount, Show } from 'solid-js'
import { useData } from '../context/data'
import {
  CREATE_CUSTOM_ROLE_MUTATION,
  DELETE_CUSTOM_ROLE_MUTATION,
  GET_COMMUNITY_ROLES_QUERY
} from '../graphql/queries'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/RoleManager.module.css'

interface Role {
  id: string
  name: string
  description: string
  icon: string
}

interface RoleSettings {
  default_roles: string[]
  available_roles: string[]
}

interface RoleManagerProps {
  communityId?: number
  roleSettings: RoleSettings
  onRoleSettingsChange: (settings: RoleSettings) => void
  customRoles: Role[]
  onCustomRolesChange: (roles: Role[]) => void
}

const STANDARD_ROLES = [
  { id: 'reader', name: 'Читатель', description: 'Может читать и комментировать', icon: '👁️' },
  { id: 'author', name: 'Автор', description: 'Может создавать публикации', icon: '✍️' },
  { id: 'artist', name: 'Художник', description: 'Может быть credited artist', icon: '🎨' },
  { id: 'expert', name: 'Эксперт', description: 'Может добавлять доказательства', icon: '🧠' },
  { id: 'editor', name: 'Редактор', description: 'Может модерировать контент', icon: '📝' },
  { id: 'admin', name: 'Администратор', description: 'Полные права', icon: '👑' }
]

const RoleManager = (props: RoleManagerProps) => {
  const { queryGraphQL } = useData()
  const [showAddRole, setShowAddRole] = createSignal(false)
  const [newRole, setNewRole] = createSignal<Role>({ id: '', name: '', description: '', icon: '🔖' })
  const [errors, setErrors] = createSignal<Record<string, string>>({})

  // Загружаем роли при монтировании компонента
  onMount(async () => {
    if (props.communityId) {
      try {
        const rolesData = await queryGraphQL(GET_COMMUNITY_ROLES_QUERY, {
          community: props.communityId
        })

        if (rolesData?.adminGetRoles) {
          const standardRoleIds = STANDARD_ROLES.map((r) => r.id)
          const customRolesList = rolesData.adminGetRoles
            .filter((role: Role) => !standardRoleIds.includes(role.id))
            .map((role: Role) => ({
              id: role.id,
              name: role.name,
              description: role.description || '',
              icon: '🔖'
            }))
          props.onCustomRolesChange(customRolesList)
        }
      } catch (error) {
        console.error('Ошибка загрузки ролей:', error)
      }
    }
  })

  const getAllRoles = () => [...STANDARD_ROLES, ...props.customRoles]

  const isRoleDisabled = (roleId: string) => roleId === 'admin'

  const validateNewRole = (): boolean => {
    const role = newRole()
    const newErrors: Record<string, string> = {}

    if (!role.id.trim()) {
      newErrors.newRoleId = 'ID роли обязательно'
    } else if (!/^[a-z0-9_-]+$/.test(role.id)) {
      newErrors.newRoleId = 'ID может содержать только латинские буквы, цифры, дефисы и подчеркивания'
    } else if (getAllRoles().some((r) => r.id === role.id)) {
      newErrors.newRoleId = 'Роль с таким ID уже существует'
    }

    if (!role.name.trim()) {
      newErrors.newRoleName = 'Название роли обязательно'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const addCustomRole = async () => {
    if (!validateNewRole()) return

    const role = newRole()

    if (props.communityId) {
      try {
        const result = await queryGraphQL(CREATE_CUSTOM_ROLE_MUTATION, {
          role: {
            id: role.id,
            name: role.name,
            description: role.description,
            icon: role.icon,
            community_id: props.communityId
          }
        })

        if (result?.adminCreateCustomRole?.success) {
          props.onCustomRolesChange([...props.customRoles, role])

          props.onRoleSettingsChange({
            ...props.roleSettings,
            available_roles: [...props.roleSettings.available_roles, role.id]
          })

          resetNewRoleForm()
        } else {
          setErrors({ newRoleId: result?.adminCreateCustomRole?.error || 'Ошибка создания роли' })
        }
      } catch (error) {
        console.error('Ошибка создания роли:', error)
        setErrors({ newRoleId: 'Ошибка создания роли' })
      }
    } else {
      props.onCustomRolesChange([...props.customRoles, role])
      props.onRoleSettingsChange({
        ...props.roleSettings,
        available_roles: [...props.roleSettings.available_roles, role.id]
      })
      resetNewRoleForm()
    }
  }

  const removeCustomRole = async (roleId: string) => {
    if (props.communityId) {
      try {
        const result = await queryGraphQL(DELETE_CUSTOM_ROLE_MUTATION, {
          role_id: roleId,
          community_id: props.communityId
        })

        if (result?.adminDeleteCustomRole?.success) {
          updateRolesAfterRemoval(roleId)
        } else {
          console.error('Ошибка удаления роли:', result?.adminDeleteCustomRole?.error)
        }
      } catch (error) {
        console.error('Ошибка удаления роли:', error)
      }
    } else {
      updateRolesAfterRemoval(roleId)
    }
  }

  const updateRolesAfterRemoval = (roleId: string) => {
    props.onCustomRolesChange(props.customRoles.filter((r) => r.id !== roleId))
    props.onRoleSettingsChange({
      available_roles: props.roleSettings.available_roles.filter((r) => r !== roleId),
      default_roles: props.roleSettings.default_roles.filter((r) => r !== roleId)
    })
  }

  const resetNewRoleForm = () => {
    setNewRole({ id: '', name: '', description: '', icon: '🔖' })
    setShowAddRole(false)
    setErrors({})
  }

  const toggleAvailableRole = (roleId: string) => {
    if (isRoleDisabled(roleId)) return

    const current = props.roleSettings
    const newAvailable = current.available_roles.includes(roleId)
      ? current.available_roles.filter((r) => r !== roleId)
      : [...current.available_roles, roleId]

    const newDefault = newAvailable.includes(roleId)
      ? current.default_roles
      : current.default_roles.filter((r) => r !== roleId)

    props.onRoleSettingsChange({
      available_roles: newAvailable,
      default_roles: newDefault
    })
  }

  const toggleDefaultRole = (roleId: string) => {
    if (isRoleDisabled(roleId)) return

    const current = props.roleSettings
    const newDefault = current.default_roles.includes(roleId)
      ? current.default_roles.filter((r) => r !== roleId)
      : [...current.default_roles, roleId]

    props.onRoleSettingsChange({
      ...current,
      default_roles: newDefault
    })
  }

  return (
    <div class={styles.roleManager}>
      {/* Доступные роли */}
      <div class={styles.section}>
        <div class={styles.sectionHeader}>
          <h3 class={styles.sectionTitle}>
            <span class={styles.icon}>🎭</span>
            Доступные роли в сообществе
          </h3>
        </div>
        <p class={styles.sectionDescription}>
          Выберите роли, которые могут быть назначены в этом сообществе
        </p>

        <div class={styles.rolesGrid}>
          <For each={getAllRoles()}>
            {(role) => (
              <div
                class={`${styles.roleCard} ${props.roleSettings.available_roles.includes(role.id) ? styles.selected : ''} ${isRoleDisabled(role.id) ? styles.disabled : ''}`}
                onClick={() => !isRoleDisabled(role.id) && toggleAvailableRole(role.id)}
              >
                <div class={styles.roleHeader}>
                  <span class={styles.roleIcon}>{role.icon}</span>
                  <div class={styles.roleActions}>
                    <Show when={props.customRoles.some((r) => r.id === role.id)}>
                      <button
                        type="button"
                        class={styles.removeButton}
                        onClick={(e) => {
                          e.stopPropagation()
                          void removeCustomRole(role.id)
                        }}
                      >
                        ❌
                      </button>
                    </Show>
                    <div class={styles.checkbox}>
                      <input
                        type="checkbox"
                        checked={props.roleSettings.available_roles.includes(role.id)}
                        disabled={isRoleDisabled(role.id)}
                        onChange={() => toggleAvailableRole(role.id)}
                      />
                    </div>
                  </div>
                </div>
                <div class={styles.roleContent}>
                  <div class={styles.roleName}>{role.name}</div>
                  <div class={styles.roleDescription}>{role.description}</div>
                  <Show when={isRoleDisabled(role.id)}>
                    <div class={styles.disabledNote}>Системная роль</div>
                  </Show>
                </div>
              </div>
            )}
          </For>
        </div>

        <div class={styles.addRoleForm}>
          {/* Форма добавления новой роли */}
          <Show
            when={showAddRole()}
            fallback={
              <button type="button" class={styles.addButton} onClick={() => setShowAddRole(true)}>
                <span>➕</span>
                Добавить роль
              </button>
            }
          >
            <h4 class={styles.addRoleTitle}>Добавить новую роль</h4>

            <div class={styles.addRoleFields}>
              <div class={styles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>🆔</span>
                    ID роли
                    <span class={formStyles.required}>*</span>
                  </span>
                </label>
                <input
                  type="text"
                  class={`${formStyles.input} ${errors().newRoleId ? formStyles.error : ''}`}
                  value={newRole().id}
                  onInput={(e) => setNewRole((prev) => ({ ...prev, id: e.currentTarget.value }))}
                  placeholder="my_custom_role"
                />
                <Show when={errors().newRoleId}>
                  <span class={formStyles.fieldError}>
                    <span class={formStyles.errorIcon}>⚠️</span>
                    {errors().newRoleId}
                  </span>
                </Show>
              </div>

              <div class={styles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>📝</span>
                    Название
                    <span class={formStyles.required}>*</span>
                  </span>
                </label>
                <input
                  type="text"
                  class={`${formStyles.input} ${errors().newRoleName ? formStyles.error : ''}`}
                  value={newRole().name}
                  onInput={(e) => setNewRole((prev) => ({ ...prev, name: e.currentTarget.value }))}
                  placeholder="Моя роль"
                />
                <Show when={errors().newRoleName}>
                  <span class={formStyles.fieldError}>
                    <span class={formStyles.errorIcon}>⚠️</span>
                    {errors().newRoleName}
                  </span>
                </Show>
              </div>

              <div class={styles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>📄</span>
                    Описание
                  </span>
                </label>
                <input
                  type="text"
                  class={formStyles.input}
                  value={newRole().description}
                  onInput={(e) => setNewRole((prev) => ({ ...prev, description: e.currentTarget.value }))}
                  placeholder="Описание роли"
                />
              </div>

              <div class={styles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>🎭</span>
                    Иконка
                  </span>
                </label>
                <input
                  type="text"
                  class={formStyles.input}
                  value={newRole().icon}
                  onInput={(e) => setNewRole((prev) => ({ ...prev, icon: e.currentTarget.value }))}
                  placeholder="🔖"
                />
              </div>
            </div>

            <div class={styles.addRoleActions}>
              <button type="button" class={styles.cancelButton} onClick={resetNewRoleForm}>
                Отмена
              </button>
              <button type="button" class={styles.primaryButton} onClick={addCustomRole}>
                Добавить роль
              </button>
            </div>
          </Show>
        </div>
      </div>

      {/* Дефолтные роли */}
      <div class={styles.section}>
        <h3 class={styles.sectionTitle}>
          <span class={styles.icon}>⭐</span>
          Дефолтные роли для новых пользователей
          <span class={styles.required}>*</span>
        </h3>
        <p class={styles.sectionDescription}>
          Роли, которые автоматически назначаются при вступлении в сообщество
        </p>

        <div class={styles.rolesGrid}>
          <For each={getAllRoles().filter((role) => props.roleSettings.available_roles.includes(role.id))}>
            {(role) => (
              <div
                class={`${styles.roleCard} ${props.roleSettings.default_roles.includes(role.id) ? styles.selected : ''} ${isRoleDisabled(role.id) ? styles.disabled : ''}`}
                onClick={() => !isRoleDisabled(role.id) && toggleDefaultRole(role.id)}
              >
                <div class={styles.roleHeader}>
                  <span class={styles.roleIcon}>{role.icon}</span>
                  <div class={styles.checkbox}>
                    <input
                      type="checkbox"
                      checked={props.roleSettings.default_roles.includes(role.id)}
                      disabled={isRoleDisabled(role.id)}
                      onChange={() => toggleDefaultRole(role.id)}
                    />
                  </div>
                </div>
                <div class={styles.roleContent}>
                  <div class={styles.roleName}>{role.name}</div>
                  <Show when={isRoleDisabled(role.id)}>
                    <div class={styles.disabledNote}>Системная роль</div>
                  </Show>
                </div>
              </div>
            )}
          </For>
        </div>
      </div>
    </div>
  )
}

export default RoleManager
