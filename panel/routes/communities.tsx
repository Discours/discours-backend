import { Component, createSignal, For, onMount, Show } from 'solid-js'
import { DELETE_COMMUNITY_MUTATION, UPDATE_COMMUNITY_MUTATION } from '../graphql/mutations'
import { GET_COMMUNITIES_QUERY } from '../graphql/queries'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

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
  const [editModal, setEditModal] = createSignal<{ show: boolean; community: Community | null }>({
    show: false,
    community: null
  })
  const [deleteModal, setDeleteModal] = createSignal<{ show: boolean; community: Community | null }>({
    show: false,
    community: null
  })

  // Форма для редактирования
  const [formData, setFormData] = createSignal({
    slug: '',
    name: '',
    desc: '',
    pic: ''
  })

  /**
   * Загружает список всех сообществ
   */
  const loadCommunities = async () => {
    setLoading(true)
    try {
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

      setCommunities(result.data.get_communities_all || [])
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
   * Открывает модалку редактирования
   */
  const openEditModal = (community: Community) => {
    setFormData({
      slug: community.slug,
      name: community.name,
      desc: community.desc || '',
      pic: community.pic
    })
    setEditModal({ show: true, community })
  }

  /**
   * Обновляет сообщество
   */
  const updateCommunity = async () => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: UPDATE_COMMUNITY_MUTATION,
          variables: { community_input: formData() }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.update_community.error) {
        throw new Error(result.data.update_community.error)
      }

      props.onSuccess('Сообщество успешно обновлено')
      setEditModal({ show: false, community: null })
      await loadCommunities()
    } catch (error) {
      props.onError(`Ошибка обновления сообщества: ${(error as Error).message}`)
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

  // Загружаем сообщества при монтировании компонента
  onMount(() => {
    void loadCommunities()
  })

  return (
    <div class={styles.container}>
      <div class={styles.header}>
        <h2>Управление сообществами</h2>
        <Button onClick={loadCommunities} disabled={loading()}>
          {loading() ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

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
              <th>ID</th>
              <th>Название</th>
              <th>Slug</th>
              <th>Описание</th>
              <th>Создатель</th>
              <th>Публикации</th>
              <th>Подписчики</th>
              <th>Авторы</th>
              <th>Создано</th>
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
                  <td>{community.created_by.name || community.created_by.email}</td>
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

      {/* Модальное окно редактирования */}
      <Modal
        isOpen={editModal().show}
        onClose={() => setEditModal({ show: false, community: null })}
        title={`Редактирование сообщества: ${editModal().community?.name || ''}`}
      >
        <div style={{ padding: '20px' }}>
          <div style={{ 'margin-bottom': '16px' }}>
            <label style={{ display: 'block', 'margin-bottom': '4px', 'font-weight': 'bold' }}>Slug</label>
            <input
              type="text"
              value={formData().slug}
              onInput={(e) => setFormData((prev) => ({ ...prev, slug: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                'border-radius': '4px'
              }}
              required
            />
          </div>

          <div style={{ 'margin-bottom': '16px' }}>
            <label style={{ display: 'block', 'margin-bottom': '4px', 'font-weight': 'bold' }}>
              Название
            </label>
            <input
              type="text"
              value={formData().name}
              onInput={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                'border-radius': '4px'
              }}
            />
          </div>

          <div style={{ 'margin-bottom': '16px' }}>
            <label style={{ display: 'block', 'margin-bottom': '4px', 'font-weight': 'bold' }}>
              Описание
            </label>
            <textarea
              value={formData().desc}
              onInput={(e) => setFormData((prev) => ({ ...prev, desc: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                'border-radius': '4px',
                'min-height': '80px',
                resize: 'vertical'
              }}
              placeholder="Описание сообщества..."
            />
          </div>

          <div style={{ 'margin-bottom': '16px' }}>
            <label style={{ display: 'block', 'margin-bottom': '4px', 'font-weight': 'bold' }}>
              Картинка (URL)
            </label>
            <input
              type="text"
              value={formData().pic}
              onInput={(e) => setFormData((prev) => ({ ...prev, pic: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                'border-radius': '4px'
              }}
              placeholder="https://example.com/image.jpg"
            />
          </div>

          <div class={styles['modal-actions']}>
            <Button variant="secondary" onClick={() => setEditModal({ show: false, community: null })}>
              Отмена
            </Button>
            <Button variant="primary" onClick={updateCommunity}>
              Сохранить
            </Button>
          </div>
        </div>
      </Modal>

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
