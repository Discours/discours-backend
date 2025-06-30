import { Component, createSignal, For, onMount, Show } from 'solid-js'
import {
  CREATE_COLLECTION_MUTATION,
  DELETE_COLLECTION_MUTATION,
  UPDATE_COLLECTION_MUTATION
} from '../graphql/mutations'
import { GET_COLLECTIONS_QUERY } from '../graphql/queries'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

/**
 * Интерфейс для коллекции
 */
interface Collection {
  id: number
  slug: string
  title: string
  desc?: string
  pic: string
  amount: number
  created_at: number
  published_at?: number
  created_by: {
    id: number
    name: string
    email: string
  }
}

interface CollectionsRouteProps {
  onError: (error: string) => void
  onSuccess: (message: string) => void
}

/**
 * Компонент для управления коллекциями
 */
const CollectionsRoute: Component<CollectionsRouteProps> = (props) => {
  const [collections, setCollections] = createSignal<Collection[]>([])
  const [loading, setLoading] = createSignal(false)
  const [editModal, setEditModal] = createSignal<{ show: boolean; collection: Collection | null }>({
    show: false,
    collection: null
  })
  const [deleteModal, setDeleteModal] = createSignal<{ show: boolean; collection: Collection | null }>({
    show: false,
    collection: null
  })
  const [createModal, setCreateModal] = createSignal(false)

  // Форма для редактирования/создания
  const [formData, setFormData] = createSignal({
    slug: '',
    title: '',
    desc: '',
    pic: ''
  })

  /**
   * Загружает список всех коллекций
   */
  const loadCollections = async () => {
    setLoading(true)
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: GET_COLLECTIONS_QUERY
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      setCollections(result.data.get_collections_all || [])
    } catch (error) {
      props.onError(`Ошибка загрузки коллекций: ${(error as Error).message}`)
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
  const openEditModal = (collection: Collection) => {
    setFormData({
      slug: collection.slug,
      title: collection.title,
      desc: collection.desc || '',
      pic: collection.pic
    })
    setEditModal({ show: true, collection })
  }

  /**
   * Открывает модалку создания
   */
  const openCreateModal = () => {
    setFormData({
      slug: '',
      title: '',
      desc: '',
      pic: ''
    })
    setCreateModal(true)
  }

  /**
   * Создает новую коллекцию
   */
  const createCollection = async () => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: CREATE_COLLECTION_MUTATION,
          variables: { collection_input: formData() }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.create_collection.error) {
        throw new Error(result.data.create_collection.error)
      }

      props.onSuccess('Коллекция успешно создана')
      setCreateModal(false)
      await loadCollections()
    } catch (error) {
      props.onError(`Ошибка создания коллекции: ${(error as Error).message}`)
    }
  }

  /**
   * Обновляет коллекцию
   */
  const updateCollection = async () => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: UPDATE_COLLECTION_MUTATION,
          variables: { collection_input: formData() }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.update_collection.error) {
        throw new Error(result.data.update_collection.error)
      }

      props.onSuccess('Коллекция успешно обновлена')
      setEditModal({ show: false, collection: null })
      await loadCollections()
    } catch (error) {
      props.onError(`Ошибка обновления коллекции: ${(error as Error).message}`)
    }
  }

  /**
   * Удаляет коллекцию
   */
  const deleteCollection = async (slug: string) => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: DELETE_COLLECTION_MUTATION,
          variables: { slug }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.delete_collection.error) {
        throw new Error(result.data.delete_collection.error)
      }

      props.onSuccess('Коллекция успешно удалена')
      setDeleteModal({ show: false, collection: null })
      await loadCollections()
    } catch (error) {
      props.onError(`Ошибка удаления коллекции: ${(error as Error).message}`)
    }
  }

  // Загружаем коллекции при монтировании компонента
  onMount(() => {
    void loadCollections()
  })

  return (
    <div class={styles.container}>
      <div class={styles.header}>
        <h2>Управление коллекциями</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <Button onClick={openCreateModal} variant="primary">
            Создать коллекцию
          </Button>
          <Button onClick={loadCollections} disabled={loading()}>
            {loading() ? 'Загрузка...' : 'Обновить'}
          </Button>
        </div>
      </div>

      <Show
        when={!loading()}
        fallback={
          <div class="loading-screen">
            <div class="loading-spinner" />
            <div>Загрузка коллекций...</div>
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
              <th>Создано</th>
              <th>Опубликовано</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <For each={collections()}>
              {(collection) => (
                <tr
                  onClick={() => openEditModal(collection)}
                  style={{ cursor: 'pointer' }}
                  class={styles['clickable-row']}
                >
                  <td>{collection.id}</td>
                  <td>{collection.title}</td>
                  <td>{collection.slug}</td>
                  <td>
                    <div
                      style={{
                        'max-width': '200px',
                        overflow: 'hidden',
                        'text-overflow': 'ellipsis',
                        'white-space': 'nowrap'
                      }}
                      title={collection.desc}
                    >
                      {collection.desc || '—'}
                    </div>
                  </td>
                  <td>{collection.created_by.name || collection.created_by.email}</td>
                  <td>{collection.amount}</td>
                  <td>{formatDate(collection.created_at)}</td>
                  <td>{collection.published_at ? formatDate(collection.published_at) : '—'}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleteModal({ show: true, collection })
                      }}
                      class={styles['delete-button']}
                      title="Удалить коллекцию"
                      aria-label="Удалить коллекцию"
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
      <Modal isOpen={createModal()} onClose={() => setCreateModal(false)} title="Создание новой коллекции">
        <div style={{ padding: '20px' }}>
          <div style={{ 'margin-bottom': '16px' }}>
            <label style={{ display: 'block', 'margin-bottom': '4px', 'font-weight': 'bold' }}>
              Slug <span style={{ color: 'red' }}>*</span>
            </label>
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
              placeholder="my-collection"
            />
          </div>

          <div style={{ 'margin-bottom': '16px' }}>
            <label style={{ display: 'block', 'margin-bottom': '4px', 'font-weight': 'bold' }}>
              Название <span style={{ color: 'red' }}>*</span>
            </label>
            <input
              type="text"
              value={formData().title}
              onInput={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                'border-radius': '4px'
              }}
              required
              placeholder="Моя коллекция"
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
              placeholder="Описание коллекции..."
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
            <Button variant="secondary" onClick={() => setCreateModal(false)}>
              Отмена
            </Button>
            <Button variant="primary" onClick={createCollection}>
              Создать
            </Button>
          </div>
        </div>
      </Modal>

      {/* Модальное окно редактирования */}
      <Modal
        isOpen={editModal().show}
        onClose={() => setEditModal({ show: false, collection: null })}
        title={`Редактирование коллекции: ${editModal().collection?.title || ''}`}
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
              value={formData().title}
              onInput={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
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
              placeholder="Описание коллекции..."
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
            <Button variant="secondary" onClick={() => setEditModal({ show: false, collection: null })}>
              Отмена
            </Button>
            <Button variant="primary" onClick={updateCollection}>
              Сохранить
            </Button>
          </div>
        </div>
      </Modal>

      {/* Модальное окно подтверждения удаления */}
      <Modal
        isOpen={deleteModal().show}
        onClose={() => setDeleteModal({ show: false, collection: null })}
        title="Подтверждение удаления"
      >
        <div>
          <p>
            Вы уверены, что хотите удалить коллекцию "<strong>{deleteModal().collection?.title}</strong>"?
          </p>
          <p class={styles['warning-text']}>
            Это действие нельзя отменить. Все связи с публикациями будут удалены.
          </p>
          <div class={styles['modal-actions']}>
            <Button variant="secondary" onClick={() => setDeleteModal({ show: false, collection: null })}>
              Отмена
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteModal().collection && deleteCollection(deleteModal().collection!.slug)}
            >
              Удалить
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default CollectionsRoute
