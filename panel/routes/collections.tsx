import { Component, createSignal, For, onMount, Show } from 'solid-js'
import {
  CREATE_COLLECTION_MUTATION,
  DELETE_COLLECTION_MUTATION,
  UPDATE_COLLECTION_MUTATION
} from '../graphql/mutations'
import { GET_COLLECTIONS_QUERY } from '../graphql/queries'
import CollectionEditModal from '../modals/CollectionEditModal'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import TableControls from '../ui/TableControls'

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
  const [filteredCollections, setFilteredCollections] = createSignal<Collection[]>([])
  const [loading, setLoading] = createSignal(false)
  const [searchQuery, setSearchQuery] = createSignal('')
  const [editModal, setEditModal] = createSignal<{
    show: boolean
    collection: Collection | null
  }>({
    show: false,
    collection: null
  })
  const [deleteModal, setDeleteModal] = createSignal<{
    show: boolean
    collection: Collection | null
  }>({
    show: false,
    collection: null
  })
  const [createModal, setCreateModal] = createSignal(false)

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

      const allCollections = result.data.get_collections_all || []
      setCollections(allCollections)
      filterCollections(allCollections, searchQuery())
    } catch (error) {
      props.onError(`Ошибка загрузки коллекций: ${(error as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Фильтрует коллекции по поисковому запросу
   */
  const filterCollections = (allCollections: Collection[], query: string) => {
    if (!query) {
      setFilteredCollections(allCollections)
      return
    }

    const lowerQuery = query.toLowerCase()
    const filtered = allCollections.filter(
      (collection) =>
        collection.title.toLowerCase().includes(lowerQuery) ||
        collection.slug.toLowerCase().includes(lowerQuery) ||
        collection.id.toString().includes(lowerQuery) ||
        collection.desc?.toLowerCase().includes(lowerQuery)
    )
    setFilteredCollections(filtered)
  }

  /**
   * Обрабатывает изменение поискового запроса
   */
  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    filterCollections(collections(), value)
  }

  /**
   * Обработчик поиска - применяет текущий поисковый запрос
   */
  const handleSearch = () => {
    filterCollections(collections(), searchQuery())
    console.log('[CollectionsRoute] Search triggered with query:', searchQuery())
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
    setEditModal({ show: true, collection })
  }

  /**
   * Открывает модалку создания
   */
  const openCreateModal = () => {
    setCreateModal(true)
  }

  /**
   * Обрабатывает сохранение коллекции (создание или обновление)
   */
  const handleSaveCollection = async (collectionData: Partial<Collection>) => {
    try {
      const isCreating = createModal()
      const mutation = isCreating ? CREATE_COLLECTION_MUTATION : UPDATE_COLLECTION_MUTATION

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: mutation,
          variables: { collection_input: collectionData }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const resultData = isCreating ? result.data.create_collection : result.data.update_collection
      if (resultData.error) {
        throw new Error(resultData.error)
      }

      props.onSuccess(isCreating ? 'Коллекция успешно создана' : 'Коллекция успешно обновлена')
      setCreateModal(false)
      setEditModal({ show: false, collection: null })
      await loadCollections()
    } catch (error) {
      props.onError(
        `Ошибка ${createModal() ? 'создания' : 'обновления'} коллекции: ${(error as Error).message}`
      )
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
    setFilteredCollections(collections())
  })

  return (
    <div class={styles.container}>
      <TableControls
        isLoading={loading()}
        searchValue={searchQuery()}
        onSearchChange={handleSearchChange}
        onSearch={handleSearch}
        searchPlaceholder="Поиск по названию, slug или ID..."
        actions={
          <button class={`${styles.button} ${styles.primary}`} onClick={openCreateModal}>
            Создать коллекцию
          </button>
        }
      />

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
            <For each={filteredCollections()}>
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
      <CollectionEditModal
        isOpen={createModal()}
        collection={null}
        onClose={() => setCreateModal(false)}
        onSave={handleSaveCollection}
      />

      {/* Модальное окно редактирования */}
      <CollectionEditModal
        isOpen={editModal().show}
        collection={editModal().collection}
        onClose={() => setEditModal({ show: false, collection: null })}
        onSave={handleSaveCollection}
      />

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
