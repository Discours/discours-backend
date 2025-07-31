import { createEffect, createSignal, Show } from 'solid-js'
import { useData } from '../context/data'
import type { Role } from '../graphql/generated/schema'
import {
  GET_COMMUNITY_ROLE_SETTINGS_QUERY,
  GET_COMMUNITY_ROLES_QUERY,
  UPDATE_COMMUNITY_ROLE_SETTINGS_MUTATION
} from '../graphql/queries'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/Modal.module.css'
import Button from '../ui/Button'
import HTMLEditor from '../ui/HTMLEditor'
import Modal from '../ui/Modal'
import RoleManager from '../ui/RoleManager'

interface Community {
  id: number
  name: string
  slug: string
  desc?: string
  pic?: string
}

interface CommunityEditModalProps {
  isOpen: boolean
  community: Community | null
  onClose: () => void
  onSave: (communityData: Partial<Community>) => Promise<void>
}

interface RoleSettings {
  default_roles: string[]
  available_roles: string[]
}

interface CustomRole {
  id: string
  name: string
  description: string
  icon: string
}

const STANDARD_ROLES = [
  { id: 'reader', name: 'Читатель', description: 'Может читать и комментировать', icon: '👁️' },
  { id: 'author', name: 'Автор', description: 'Может создавать публикации', icon: '✍️' },
  { id: 'artist', name: 'Художник', description: 'Может быть credited artist', icon: '🎨' },
  { id: 'expert', name: 'Эксперт', description: 'Может добавлять доказательства', icon: '🧠' },
  { id: 'editor', name: 'Редактор', description: 'Может модерировать контент', icon: '📝' },
  { id: 'admin', name: 'Администратор', description: 'Полные права', icon: '👑' }
]

const CommunityEditModal = (props: CommunityEditModalProps) => {
  const { queryGraphQL } = useData()
  const [formData, setFormData] = createSignal<Partial<Community>>({})
  const [roleSettings, setRoleSettings] = createSignal<RoleSettings>({
    default_roles: ['reader'],
    available_roles: ['reader', 'author', 'artist', 'expert', 'editor', 'admin']
  })
  const [customRoles, setCustomRoles] = createSignal<CustomRole[]>([])
  const [errors, setErrors] = createSignal<Record<string, string>>({})
  const [activeTab, setActiveTab] = createSignal<'basic' | 'roles'>('basic')
  const [loading, setLoading] = createSignal(false)

  // Инициализация формы при открытии
  createEffect(() => {
    if (props.isOpen) {
      if (props.community) {
        setFormData({
          name: props.community.name || '',
          slug: props.community.slug || '',
          desc: props.community.desc || '',
          pic: props.community.pic || ''
        })
        void loadRoleSettings()
      } else {
        setFormData({ name: '', slug: '', desc: '', pic: '' })
        setRoleSettings({
          default_roles: ['reader'],
          available_roles: ['reader', 'author', 'artist', 'expert', 'editor', 'admin']
        })
      }
      setErrors({})
      setActiveTab('basic')
      setCustomRoles([])
    }
  })

  const loadRoleSettings = async () => {
    if (!props.community?.id) return

    try {
      const data = await queryGraphQL(GET_COMMUNITY_ROLE_SETTINGS_QUERY, {
        community_id: props.community.id
      })

      if (data?.adminGetCommunityRoleSettings && !data.adminGetCommunityRoleSettings.error) {
        setRoleSettings({
          default_roles: data.adminGetCommunityRoleSettings.default_roles,
          available_roles: data.adminGetCommunityRoleSettings.available_roles
        })
      }

      // Загружаем все роли сообщества для получения произвольных
      const rolesData = await queryGraphQL(GET_COMMUNITY_ROLES_QUERY, {
        community: props.community.id
      })

      if (rolesData?.adminGetRoles) {
        // Фильтруем только произвольные роли (не стандартные)
        const standardRoleIds = STANDARD_ROLES.map((r) => r.id)
        const customRolesList = rolesData.adminGetRoles
          .where((role: Role) => !standardRoleIds.includes(role.id))
          .map((role: Role) => ({
            id: role.id,
            name: role.name,
            description: role.description || '',
            icon: '🔖' // Пока иконки не хранятся в БД
          }))

        setCustomRoles(customRolesList)
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек ролей:', error)
    }
  }

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}
    const data = formData()

    if (!data.name?.trim()) {
      newErrors.name = 'Название обязательно'
    }

    if (!data.slug?.trim()) {
      newErrors.slug = 'Слаг обязательный'
    } else if (!/^[a-z0-9-]+$/.test(data.slug)) {
      newErrors.slug = 'Слаг может содержать только латинские буквы, цифры и дефисы'
    }

    // Валидация ролей
    const roleSet = roleSettings()
    if (roleSet.default_roles.length === 0) {
      newErrors.roles = 'Должна быть хотя бы одна дефолтная роль'
    }

    const invalidDefaults = roleSet.default_roles.where((role) => !roleSet.available_roles.includes(role))
    if (invalidDefaults.length > 0) {
      newErrors.roles = 'Дефолтные роли должны быть из списка доступных'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const handleSave = async () => {
    if (!validateForm()) {
      return
    }

    setLoading(true)
    try {
      // Сохраняем основные данные сообщества
      await props.onSave(formData())

      // Если редактируем существующее сообщество, сохраняем настройки ролей
      if (props.community?.id) {
        const roleData = await queryGraphQL(UPDATE_COMMUNITY_ROLE_SETTINGS_MUTATION, {
          community_id: props.community.id,
          default_roles: roleSettings().default_roles,
          available_roles: roleSettings().available_roles
        })

        if (!roleData?.adminUpdateCommunityRoleSettings?.success) {
          console.error(
            'Ошибка сохранения настроек ролей:',
            roleData?.adminUpdateCommunityRoleSettings?.error
          )
        }
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error)
    } finally {
      setLoading(false)
    }
  }

  const isCreating = () => props.community === null
  const modalTitle = () =>
    isCreating()
      ? 'Создание нового сообщества'
      : `Редактирование сообщества: ${props.community?.name || ''}`

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title={modalTitle()} size="large">
      <div class={styles.content}>
        {/* Табы */}
        <div class={formStyles.tabs}>
          <button
            type="button"
            class={`${formStyles.tab} ${activeTab() === 'basic' ? formStyles.active : ''}`}
            onClick={() => setActiveTab('basic')}
          >
            <span class={formStyles.tabIcon}>⚙️</span>
            Основные настройки
          </button>
          <Show when={!isCreating()}>
            <button
              type="button"
              class={`${formStyles.tab} ${activeTab() === 'roles' ? formStyles.active : ''}`}
              onClick={() => setActiveTab('roles')}
            >
              <span class={formStyles.tabIcon}>👥</span>
              Роли и права
            </button>
          </Show>
        </div>

        {/* Контент табов */}
        <div class={formStyles.content}>
          <Show when={activeTab() === 'basic'}>
            <div class={formStyles.form}>
              <div class={formStyles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>🏷️</span>
                    Название сообщества
                    <span class={formStyles.required}>*</span>
                  </span>
                </label>
                <input
                  type="text"
                  class={`${formStyles.input} ${errors().name ? formStyles.error : ''}`}
                  value={formData().name || ''}
                  onInput={(e) => updateField('name', e.currentTarget.value)}
                  placeholder="Введите название сообщества"
                />
                <Show when={errors().name}>
                  <span class={formStyles.fieldError}>
                    <span class={formStyles.errorIcon}>⚠️</span>
                    {errors().name}
                  </span>
                </Show>
              </div>

              <div class={formStyles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>🔗</span>
                    Слаг
                    <span class={formStyles.required}>*</span>
                  </span>
                </label>
                <input
                  type="text"
                  class={`${formStyles.input} ${errors().slug ? formStyles.error : ''} ${!isCreating() ? formStyles.disabled : ''}`}
                  value={formData().slug || ''}
                  onInput={(e) => updateField('slug', e.currentTarget.value)}
                  placeholder="community-slug"
                  disabled={!isCreating()}
                />
                <Show when={errors().slug}>
                  <span class={formStyles.fieldError}>
                    <span class={formStyles.errorIcon}>⚠️</span>
                    {errors().slug}
                  </span>
                </Show>
                <Show when={!isCreating()}>
                  <span class={formStyles.hint}>
                    <span class={formStyles.hintIcon}>💡</span>
                    Слаг нельзя изменить после создания
                  </span>
                </Show>
              </div>

              <div class={formStyles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>📝</span>
                    Описание
                  </span>
                </label>
                <HTMLEditor value={formData().desc || ''} onInput={(value) => updateField('desc', value)} />
              </div>

              <div class={formStyles.fieldGroup}>
                <label class={formStyles.label}>
                  <span class={formStyles.labelText}>
                    <span class={formStyles.labelIcon}>🖼️</span>
                    Изображение (URL)
                  </span>
                </label>
                <input
                  type="url"
                  class={formStyles.input}
                  value={formData().pic || ''}
                  onInput={(e) => updateField('pic', e.currentTarget.value)}
                  placeholder="https://example.com/image.jpg"
                />
              </div>
            </div>
          </Show>

          <Show when={activeTab() === 'roles' && !isCreating()}>
            <RoleManager
              communityId={props.community?.id}
              roleSettings={roleSettings()}
              onRoleSettingsChange={setRoleSettings}
              customRoles={customRoles()}
              onCustomRolesChange={setCustomRoles}
            />

            <Show when={errors().roles}>
              <span class={formStyles.fieldError}>
                <span class={formStyles.errorIcon}>⚠️</span>
                {errors().roles}
              </span>
            </Show>
          </Show>
        </div>

        <div class={styles.footer}>
          <Button variant="secondary" onClick={props.onClose}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={loading()}>
            <Show when={loading()}>
              <span class={formStyles.spinner} />
            </Show>
            {loading() ? 'Сохранение...' : isCreating() ? 'Создать' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default CommunityEditModal
