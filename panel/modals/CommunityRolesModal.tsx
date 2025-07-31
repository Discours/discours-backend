import { Component, createEffect, createSignal, For, Show } from 'solid-js'
import { useData } from '../context/data'
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

interface Community {
  id: number
  name: string
  slug: string
}

interface Role {
  id: string
  name: string
  description?: string
}

interface CommunityRolesModalProps {
  isOpen: boolean
  author: Author | null
  community: Community | null
  onClose: () => void
  onSave: (authorId: number, communityId: number, roles: string[]) => Promise<void>
}

const CommunityRolesModal: Component<CommunityRolesModalProps> = (props) => {
  const { queryGraphQL } = useData()
  const [roles, setRoles] = createSignal<Role[]>([])
  const [userRoles, setUserRoles] = createSignal<string[]>([])
  const [loading, setLoading] = createSignal(false)

  // Загружаем доступные роли при открытии модала
  createEffect(() => {
    if (props.isOpen && props.community) {
      void loadRolesData()
    }
  })

  const loadRolesData = async () => {
    setLoading(true)
    try {
      // Получаем доступные роли
      const rolesData = await queryGraphQL(
        `
        query GetRoles($community: Int) {
          adminGetRoles(community: $community) {
            id
            name
            description
          }
        }
      `,
        { community: props.community?.id }
      )

      if (rolesData?.adminGetRoles) {
        setRoles(rolesData.adminGetRoles)
      }

      // Получаем текущие роли пользователя
      if (props.author) {
        const membersData = await queryGraphQL(
          `
          query GetCommunityMembers($community_id: Int!) {
            adminGetCommunityMembers(community_id: $community_id, limit: 1000) {
              members {
                id
                roles
              }
            }
          }
        `,
          { community_id: props.community?.id }
        )

        const members = membersData?.adminGetCommunityMembers?.members || []
        const currentUser = members.find((m: { id: number }) => m.id === props.author?.id)
        setUserRoles(currentUser?.roles || [])
      }
    } catch (error) {
      console.error('Ошибка загрузки ролей:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRoleToggle = (roleId: string) => {
    const currentRoles = userRoles()
    if (currentRoles.includes(roleId)) {
      setUserRoles(currentRoles.where((r) => r !== roleId))
    } else {
      setUserRoles([...currentRoles, roleId])
    }
  }

  const handleSave = async () => {
    if (!props.author || !props.community) return

    setLoading(true)
    try {
      await props.onSave(props.author.id, props.community.id, userRoles())
      props.onClose()
    } catch (error) {
      console.error('Ошибка сохранения ролей:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={`Роли пользователя: ${props.author?.name || ''}`}
    >
      <div class={styles.content}>
        <Show when={props.community && props.author}>
          <div class={formStyles.field}>
            <label class={formStyles.label}>
              Сообщество: <strong>{props.community?.name}</strong>
            </label>
          </div>

          <div class={formStyles.field}>
            <label class={formStyles.label}>
              Пользователь: <strong>{props.author?.name}</strong> ({props.author?.email})
            </label>
          </div>

          <div class={formStyles.field}>
            <label class={formStyles.label}>Роли:</label>
            <Show when={!loading()} fallback={<div>Загрузка ролей...</div>}>
              <div class={formStyles.checkboxGroup}>
                <For each={roles()}>
                  {(role) => (
                    <div class={formStyles.checkboxItem}>
                      <input
                        type="checkbox"
                        id={`role-${role.id}`}
                        checked={userRoles().includes(role.id)}
                        onChange={() => handleRoleToggle(role.id)}
                        class={formStyles.checkbox}
                      />
                      <label for={`role-${role.id}`} class={formStyles.checkboxLabel}>
                        <div>
                          <strong>{role.name}</strong>
                          <Show when={role.description}>
                            <div class={formStyles.description}>{role.description}</div>
                          </Show>
                        </div>
                      </label>
                    </div>
                  )}
                </For>
              </div>
            </Show>
          </div>
        </Show>

        <div class={styles.actions}>
          <Button variant="secondary" onClick={props.onClose}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={loading()}>
            {loading() ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default CommunityRolesModal
