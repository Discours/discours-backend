import { Component, createEffect, createSignal, For, on, onMount, Show, untrack } from 'solid-js'
import { useTableSort } from '../context/sort'
import { COMMUNITIES_SORT_CONFIG } from '../context/sortConfig'
import {
  CREATE_COMMUNITY_MUTATION,
  DELETE_COMMUNITY_MUTATION,
  UPDATE_COMMUNITY_MUTATION
} from '../graphql/mutations'
import { GET_COMMUNITIES_QUERY } from '../graphql/queries'
import CommunityEditModal from '../modals/CommunityEditModal'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import SortableHeader from '../ui/SortableHeader'
import TableControls from '../ui/TableControls'

/**
 * Интерфейс для сообщества (используем локальный интерфейс для совместимости)
 */
interface Community {
  id: number
  slug: string
  name: string
  desc?: string
  pic: string
  created_at: number
  created_by?: {  // Делаем created_by необязательным
    id: number
    name: string
    email: string
  } | null
  stat: {
    shouts: number
    followers: number
    authors: number
  }
}

interface CommunitiesRouteProps {
  onError: (error: string) => void
  onSuccess: (message: string) => void
}

/**
 * Компонент для управления сообществами
 */
const CommunitiesRoute: Component<CommunitiesRouteProps> = (props) => {
  const [communities, setCommunities] = createSignal<Community[]>([])
  const [loading, setLoading] = createSignal(false)
  const { sortState } = useTableSort()
  const [editModal, setEditModal] = createSignal<{
    show: boolean
    community: Community | null
  }>({
    show: false,
    community: null
  })
  const [deleteModal, setDeleteModal] = createSignal<{
    show: boolean
    community: Community | null
  }>({
    show: false,
    community: null
  })
  const [createModal, setCreateModal] = createSignal<{ show: boolean }>({
    show: false
  })

  /**
   * Загружает список всех сообществ
   */
  const loadCommunities = async () => {
    setLoading(true)
    try {
      // Загружаем все сообщества без параметров сортировки
      // Сортировка будет выполнена на клиенте
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: GET_COMMUNITIES_QUERY
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      // Получаем данные и сортируем их на клиенте
      const communitiesData = result.data.get_communities_all || []
      const sortedCommunities = sortCommunities(communitiesData)
      setCommunities(sortedCommunities)
    } catch (error) {
      props.onError(`Ошибка загрузки сообществ: ${(error as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Форматирует дату
   */
  const formatDate = (timestamp: number): string => {
    return new Date(timestamp * 1000).toLocaleDateString('ru-RU')
  }

  /**
   * Сортирует сообщества на клиенте в соответствии с текущим состоянием сортировки
   */
  const sortCommunities = (communities: Community[]): Community[] => {
    const { field, direction } = sortState()

    return [...communities].sort((a, b) => {
      let comparison = 0

      switch (field) {
        case 'id':
          comparison = a.id - b.id
          break
        case 'name':
          comparison = (a.name || '').localeCompare(b.name || '', 'ru')
          break
        case 'slug':
          comparison = (a.slug || '').localeCompare(b.slug || '', 'ru')
          break
        case 'created_at':
          comparison = a.created_at - b.created_at
          break
        case 'created_by': {
          const aName = a.created_by?.name || a.created_by?.email || ''
          const bName = b.created_by?.name || b.created_by?.email || ''
          comparison = aName.localeCompare(bName, 'ru')
          break
        }
        case 'shouts':
          comparison = (a.stat?.shouts || 0) - (b.stat?.shouts || 0)
          break
        case 'followers':
          comparison = (a.stat?.followers || 0) - (b.stat?.followers || 0)
          break
        case 'authors':
          comparison = (a.stat?.authors || 0) - (b.stat?.authors || 0)
          break
        default:
          comparison = a.id - b.id
      }

      return direction === 'desc' ? -comparison : comparison
    })
  }

  /**
   * Открывает модалку создания
   */
  const openCreateModal = () => {
    setCreateModal({ show: true })
  }

  /**
   * Открывает модалку редактирования
   */
  const openEditModal = (community: Community) => {
    setEditModal({ show: true, community })
  }

  /**
   * Обрабатывает сохранение сообщества (создание или обновление)
   */
  const handleSaveCommunity = async (communityData: Partial<Community>) => {
    try {
      const isCreating = !editModal().community && createModal().show
      const mutation = isCreating ? CREATE_COMMUNITY_MUTATION : UPDATE_COMMUNITY_MUTATION

      // Удаляем created_by, если он null или undefined
      if (communityData.created_by === null || communityData.created_by === undefined) {
        delete communityData.created_by
      }

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: mutation,
          variables: { community_input: communityData }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const resultData = isCreating ? result.data.create_community : result.data.update_community
      if (resultData.error) {
        throw new Error(resultData.error)
      }

      props.onSuccess(isCreating ? 'Сообщество успешно создано' : 'Сообщество успешно обновлено')
      setCreateModal({ show: false })
      setEditModal({ show: false, community: null })
      await loadCommunities()
    } catch (error) {
      props.onError(
        `Ошибка ${createModal().show ? 'создания' : 'обновления'} сообщества: ${(error as Error).message}`
      )
    }
  }

  /**
   * Удаляет сообщество
   */
  const deleteCommunity = async (slug: string) => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: DELETE_COMMUNITY_MUTATION,
          variables: { slug }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.delete_community.error) {
        throw new Error(result.data.delete_community.error)
      }

      props.onSuccess('Сообщество успешно удалено')
      setDeleteModal({ show: false, community: null })
      await loadCommunities()
    } catch (error) {
      props.onError(`Ошибка удаления сообщества: ${(error as Error).message}`)
    }
  }

  // Пересортировка при изменении состояния сортировки
  createEffect(
    on([sortState], () => {
      if (communities().length > 0) {
        // Используем untrack для предотвращения бесконечной рекурсии
        const currentCommunities = untrack(() => communities())
        const sortedCommunities = sortCommunities(currentCommunities)

        // Сравниваем текущий порядок с отсортированным, чтобы избежать лишних обновлений
        const needsUpdate =
          JSON.stringify(currentCommunities.map((c: Community) => c.id)) !==
          JSON.stringify(sortedCommunities.map((c: Community) => c.id))

        if (needsUpdate) {
          setCommunities(sortedCommunities)
        }
      }
    })
  )

  // Загружаем сообщества при монтировании компонента
  onMount(() => {
    void loadCommunities()
  })

  return (
    <div class={styles.container}>
      <TableControls
        onRefresh={loadCommunities}
        isLoading={loading()}
        actions={
          <Button variant="primary" onClick={openCreateModal}>
            Создать сообщество
          </Button>
        }
      />

      <Show
        when={!loading()}
        fallback={
          <div class="loading-screen">
            <div class="loading-spinner" />
            <div>Загрузка сообществ...</div>
          </div>
        }
      >
        <table class={styles.table}>
          <thead>
            <tr>
              <SortableHeader field="id" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                ID
              </SortableHeader>
              <SortableHeader field="name" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                Название
              </SortableHeader>
              <SortableHeader field="slug" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                Slug
              </SortableHeader>
              <th>Описание</th>
              <SortableHeader field="created_by" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                Создатель
              </SortableHeader>
              <SortableHeader field="shouts" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                Публикации
              </SortableHeader>
              <SortableHeader field="followers" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                Подписчики
              </SortableHeader>
              <th>Авторы</th>
              <SortableHeader field="created_at" allowedFields={COMMUNITIES_SORT_CONFIG.allowedFields}>
                Создано
              </SortableHeader>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <For each={communities()}>
              {(community) => (
                <tr
                  onClick={() => openEditModal(community)}
                  style={{ cursor: 'pointer' }}
                  class={styles['clickable-row']}
                >
                  <td>{community.id}</td>
                  <td>{community.name}</td>
                  <td>{community.slug}</td>
                  <td>
                    <div
                      style={{
                        'max-width': '200px',
                        overflow: 'hidden',
                        'text-overflow': 'ellipsis',
                        'white-space': 'nowrap'
                      }}
                      title={community.desc}
                    >
                      {community.desc || '—'}
                    </div>
                  </td>
                  <td>
                    <Show when={community.created_by} fallback={<span>—</span>}>
                      <span>{community.created_by?.name || community.created_by?.email || ''}</span>
                    </Show>
                  </td>
                  <td>{community.stat.shouts}</td>
                  <td>{community.stat.followers}</td>
                  <td>{community.stat.authors}</td>
                  <td>{formatDate(community.created_at)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleteModal({ show: true, community })
                      }}
                      class={styles['delete-button']}
                      title="Удалить сообщество"
                      aria-label="Удалить сообщество"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </Show>

      {/* Модальное окно создания */}
      <CommunityEditModal
        isOpen={createModal().show}
        community={null}
        onClose={() => setCreateModal({ show: false })}
        onSave={handleSaveCommunity}
      />

      {/* Модальное окно редактирования */}
      <CommunityEditModal
        isOpen={editModal().show}
        community={editModal().community}
        onClose={() => setEditModal({ show: false, community: null })}
        onSave={handleSaveCommunity}
      />

      {/* Модальное окно подтверждения удаления */}
      <Modal
        isOpen={deleteModal().show}
        onClose={() => setDeleteModal({ show: false, community: null })}
        title="Подтверждение удаления"
      >
        <div>
          <p>
            Вы уверены, что хотите удалить сообщество "<strong>{deleteModal().community?.name}</strong>"?
          </p>
          <p class={styles['warning-text']}>
            Это действие нельзя отменить. Все публикации и темы сообщества могут быть затронуты.
          </p>
          <div class={styles['modal-actions']}>
            <Button variant="secondary" onClick={() => setDeleteModal({ show: false, community: null })}>
              Отмена
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteModal().community && deleteCommunity(deleteModal().community!.slug)}
            >
              Удалить
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default CommunitiesRoute
