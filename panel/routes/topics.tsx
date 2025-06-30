/**
 * Компонент управления топиками
 * @module TopicsRoute
 */

import { Component, createEffect, createSignal, For, JSX, on, onMount, Show, untrack } from 'solid-js'
import { query } from '../graphql'
import type { Query } from '../graphql/generated/schema'
import { CREATE_TOPIC_MUTATION, DELETE_TOPIC_MUTATION, UPDATE_TOPIC_MUTATION } from '../graphql/mutations'
import { GET_TOPICS_QUERY } from '../graphql/queries'
import TopicEditModal from '../modals/TopicEditModal'
import TopicMergeModal from '../modals/TopicMergeModal'
import TopicSimpleParentModal from '../modals/TopicSimpleParentModal'
import styles from '../styles/Table.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

/**
 * Интерфейс топика
 */
interface Topic {
  id: number
  slug: string
  title: string
  body?: string
  pic?: string
  community: number
  parent_ids?: number[]
  children?: Topic[]
  level?: number
}

/**
 * Интерфейс свойств компонента
 */
interface TopicsRouteProps {
  onError: (error: string) => void
  onSuccess: (message: string) => void
}

/**
 * Компонент управления топиками
 */
const TopicsRoute: Component<TopicsRouteProps> = (props) => {
  const [rawTopics, setRawTopics] = createSignal<Topic[]>([])
  const [topics, setTopics] = createSignal<Topic[]>([])
  const [loading, setLoading] = createSignal(false)
  const [sortBy, setSortBy] = createSignal<'id' | 'title'>('id')
  const [sortDirection, setSortDirection] = createSignal<'asc' | 'desc'>('asc')
  const [deleteModal, setDeleteModal] = createSignal<{ show: boolean; topic: Topic | null }>({
    show: false,
    topic: null
  })
  const [editModal, setEditModal] = createSignal<{ show: boolean; topic: Topic | null }>({
    show: false,
    topic: null
  })
  const [createModal, setCreateModal] = createSignal<{ show: boolean }>({
    show: false
  })
  const [selectedTopics, setSelectedTopics] = createSignal<number[]>([])
  const [groupAction, setGroupAction] = createSignal<'delete' | 'merge' | ''>('')
  const [mergeModal, setMergeModal] = createSignal<{ show: boolean }>({
    show: false
  })
  const [simpleParentModal, setSimpleParentModal] = createSignal<{ show: boolean; topic: Topic | null }>({
    show: false,
    topic: null
  })

  /**
   * Загружает список всех топиков
   */
  const loadTopics = async () => {
    setLoading(true)
    try {
      const data = await query<{ get_topics_all: Query['get_topics_all'] }>(
        `${location.origin}/graphql`,
        GET_TOPICS_QUERY
      )

      if (data?.get_topics_all) {
        // Строим иерархическую структуру
        const validTopics = data.get_topics_all.filter((topic): topic is Topic => topic !== null)
        setRawTopics(validTopics)
      }
    } catch (error) {
      props.onError(`Ошибка загрузки топиков: ${(error as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  // Пересортировка при изменении rawTopics или параметров сортировки
  createEffect(
    on([rawTopics, sortBy, sortDirection], () => {
      const rawData = rawTopics()
      const sort = sortBy()
      const direction = sortDirection()

      if (rawData.length > 0) {
        // Используем untrack для чтения buildHierarchy без дополнительных зависимостей
        const hierarchicalTopics = untrack(() => buildHierarchy(rawData, sort, direction))
        setTopics(hierarchicalTopics)
      } else {
        setTopics([])
      }
    })
  )

  // Загружаем топики при монтировании компонента
  onMount(() => {
    void loadTopics()
  })

  /**
   * Строит иерархическую структуру топиков
   */
  const buildHierarchy = (
    flatTopics: Topic[],
    sortField?: 'id' | 'title',
    sortDir?: 'asc' | 'desc'
  ): Topic[] => {
    const topicMap = new Map<number, Topic>()
    const rootTopics: Topic[] = []

    // Создаем карту всех топиков
    flatTopics.forEach((topic) => {
      topicMap.set(topic.id, { ...topic, children: [], level: 0 })
    })

    // Строим иерархию
    flatTopics.forEach((topic) => {
      const currentTopic = topicMap.get(topic.id)!

      if (!topic.parent_ids || topic.parent_ids.length === 0) {
        // Корневой топик
        rootTopics.push(currentTopic)
      } else {
        // Находим родителя и добавляем как дочерний
        const parentId = topic.parent_ids[topic.parent_ids.length - 1]
        const parent = topicMap.get(parentId)
        if (parent) {
          currentTopic.level = (parent.level || 0) + 1
          parent.children!.push(currentTopic)
        } else {
          // Если родитель не найден, добавляем как корневой
          rootTopics.push(currentTopic)
        }
      }
    })

    return sortTopics(rootTopics, sortField, sortDir)
  }

  /**
   * Сортирует топики рекурсивно
   */
  const sortTopics = (topics: Topic[], sortField?: 'id' | 'title', sortDir?: 'asc' | 'desc'): Topic[] => {
    const field = sortField || sortBy()
    const direction = sortDir || sortDirection()

    const sortedTopics = topics.sort((a, b) => {
      let comparison = 0

      if (field === 'title') {
        comparison = (a.title || '').localeCompare(b.title || '', 'ru')
      } else {
        comparison = a.id - b.id
      }

      return direction === 'desc' ? -comparison : comparison
    })

    // Рекурсивно сортируем дочерние элементы
    sortedTopics.forEach((topic) => {
      if (topic.children && topic.children.length > 0) {
        topic.children = sortTopics(topic.children, field, direction)
      }
    })

    return sortedTopics
  }

  /**
   * Обрезает текст до указанной длины
   */
  const truncateText = (text: string, maxLength = 100): string => {
    if (!text) return '—'
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text
  }

  /**
   * Рекурсивно отображает топики с отступами для иерархии
   */
  const renderTopics = (topics: Topic[]): JSX.Element[] => {
    const result: JSX.Element[] = []

    topics.forEach((topic) => {
      const isSelected = selectedTopics().includes(topic.id)

      result.push(
        <tr class={styles['clickable-row']}>
          <td>{topic.id}</td>
          <td
            style={{ 'padding-left': `${(topic.level || 0) * 20}px`, cursor: 'pointer' }}
            onClick={() => setEditModal({ show: true, topic })}
          >
            {topic.level! > 0 && '└─ '}
            {topic.title}
          </td>
          <td onClick={() => setEditModal({ show: true, topic })} style={{ cursor: 'pointer' }}>
            {topic.slug}
          </td>
          <td onClick={() => setEditModal({ show: true, topic })} style={{ cursor: 'pointer' }}>
            <div
              style={{
                'max-width': '200px',
                overflow: 'hidden',
                'text-overflow': 'ellipsis',
                'white-space': 'nowrap'
              }}
              title={topic.body}
            >
              {truncateText(topic.body?.replace(/<[^>]*>/g, '') || '', 100)}
            </div>
          </td>
          <td onClick={() => setEditModal({ show: true, topic })} style={{ cursor: 'pointer' }}>
            {topic.community}
          </td>
          <td onClick={() => setEditModal({ show: true, topic })} style={{ cursor: 'pointer' }}>
            {topic.parent_ids?.join(', ') || '—'}
          </td>
          <td onClick={(e) => e.stopPropagation()}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => {
                e.stopPropagation()
                handleTopicSelect(topic.id, e.target.checked)
              }}
              style={{ cursor: 'pointer' }}
            />
          </td>
        </tr>
      )

      if (topic.children && topic.children.length > 0) {
        result.push(...renderTopics(topic.children))
      }
    })

    return result
  }

  /**
   * Обновляет топик
   */
  const updateTopic = async (updatedTopic: Topic) => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: UPDATE_TOPIC_MUTATION,
          variables: { topic_input: updatedTopic }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.update_topic.success) {
        props.onSuccess('Топик успешно обновлен')
        setEditModal({ show: false, topic: null })
        await loadTopics() // Перезагружаем список
      } else {
        throw new Error(result.data.update_topic.message || 'Ошибка обновления топика')
      }
    } catch (error) {
      props.onError(`Ошибка обновления топика: ${(error as Error).message}`)
    }
  }

  /**
   * Создает новый топик
   */
  const createTopic = async (newTopic: Topic) => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: CREATE_TOPIC_MUTATION,
          variables: { topic_input: newTopic }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.create_topic.error) {
        throw new Error(result.data.create_topic.error)
      }

      props.onSuccess('Топик успешно создан')
      setCreateModal({ show: false })
      await loadTopics() // Перезагружаем список
    } catch (error) {
      props.onError(`Ошибка создания топика: ${(error as Error).message}`)
    }
  }

  /**
   * Обработчик выбора/снятия выбора топика
   */
  const handleTopicSelect = (topicId: number, checked: boolean) => {
    if (checked) {
      setSelectedTopics(prev => [...prev, topicId])
    } else {
      setSelectedTopics(prev => prev.filter(id => id !== topicId))
    }
  }

  /**
   * Обработчик выбора/снятия выбора всех топиков
   */
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allTopicIds = rawTopics().map(topic => topic.id)
      setSelectedTopics(allTopicIds)
    } else {
      setSelectedTopics([])
    }
  }

  /**
   * Проверяет выбраны ли все топики
   */
  const isAllSelected = () => {
    const allIds = rawTopics().map(topic => topic.id)
    const selected = selectedTopics()
    return allIds.length > 0 && allIds.every(id => selected.includes(id))
  }

  /**
   * Проверяет выбран ли хотя бы один топик
   */
  const hasSelectedTopics = () => selectedTopics().length > 0

  /**
   * Выполняет групповое действие
   */
  const executeGroupAction = () => {
    const action = groupAction()
    const selected = selectedTopics()

    if (!action || selected.length === 0) {
      props.onError('Выберите действие и топики')
      return
    }

    if (action === 'delete') {
      // Групповое удаление
      const selectedTopicsData = rawTopics().filter(t => selected.includes(t.id))
      setDeleteModal({ show: true, topic: selectedTopicsData[0] }) // Используем первый для отображения
    } else if (action === 'merge') {
      // Слияние топиков
      if (selected.length < 2) {
        props.onError('Для слияния нужно выбрать минимум 2 темы')
        return
      }
      setMergeModal({ show: true })
    }
  }

  /**
   * Групповое удаление выбранных топиков
   */
  const deleteSelectedTopics = async () => {
    const selected = selectedTopics()
    if (selected.length === 0) return

    try {
      // Удаляем по одному (можно оптимизировать пакетным удалением)
      for (const topicId of selected) {
        await deleteTopic(topicId)
      }

      setSelectedTopics([])
      setGroupAction('')
      props.onSuccess(`Успешно удалено ${selected.length} тем`)
    } catch (error) {
      props.onError(`Ошибка группового удаления: ${(error as Error).message}`)
    }
  }

  /**
   * Удаляет топик
   */
  const deleteTopic = async (topicId: number) => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: DELETE_TOPIC_MUTATION,
          variables: { id: topicId }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      if (result.data.delete_topic_by_id.success) {
        props.onSuccess('Топик успешно удален')
        setDeleteModal({ show: false, topic: null })
        await loadTopics() // Перезагружаем список
      } else {
        throw new Error(result.data.delete_topic_by_id.message || 'Ошибка удаления топика')
      }
    } catch (error) {
      props.onError(`Ошибка удаления топика: ${(error as Error).message}`)
    }
  }

  return (
    <div class={styles.container}>
      <div class={styles.header}>
        <div style={{ display: 'flex', gap: '12px', 'align-items': 'center' }}>
          <div style={{ display: 'flex', gap: '8px', 'align-items': 'center' }}>
            <label style={{ 'font-size': '14px', color: '#666' }}>Сортировка:</label>
            <select
              value={sortBy()}
              onInput={(e) => setSortBy(e.target.value as 'id' | 'title')}
              style={{
                padding: '4px 8px',
                border: '1px solid #ddd',
                'border-radius': '4px',
                'font-size': '14px'
              }}
            >
              <option value="id">По ID</option>
              <option value="title">По названию</option>
            </select>
            <select
              value={sortDirection()}
              onInput={(e) => setSortDirection(e.target.value as 'asc' | 'desc')}
              style={{
                padding: '4px 8px',
                border: '1px solid #ddd',
                'border-radius': '4px',
                'font-size': '14px'
              }}
            >
              <option value="asc">↑ По возрастанию</option>
              <option value="desc">↓ По убыванию</option>
            </select>
          </div>
          <Button onClick={loadTopics} disabled={loading()}>
            {loading() ? 'Загрузка...' : 'Обновить'}
          </Button>
          <Button variant="primary" onClick={() => setCreateModal({ show: true })}>
            Создать тему
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              if (selectedTopics().length === 1) {
                const selectedTopic = rawTopics().find(t => t.id === selectedTopics()[0])
                if (selectedTopic) {
                  setSimpleParentModal({ show: true, topic: selectedTopic })
                }
              } else {
                props.onError('Выберите одну тему для назначения родителя')
              }
            }}
          >
            🏠 Назначить родителя
          </Button>
        </div>
      </div>

      <Show
        when={!loading()}
        fallback={
          <div class="loading-screen">
            <div class="loading-spinner" />
            <div>Загрузка топиков...</div>
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
              <th>Сообщество</th>
              <th>Родители</th>
              <th>
                <div style={{ display: 'flex', 'align-items': 'center', gap: '8px', 'flex-direction': 'column' }}>
                  <div style={{ display: 'flex', 'align-items': 'center', gap: '4px' }}>
                    <input
                      type="checkbox"
                      checked={isAllSelected()}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      style={{ cursor: 'pointer' }}
                      title="Выбрать все"
                    />
                    <span style={{ 'font-size': '12px' }}>Все</span>
                  </div>
                  <Show when={hasSelectedTopics()}>
                    <div style={{ display: 'flex', gap: '4px', 'align-items': 'center' }}>
                      <select
                        value={groupAction()}
                        onChange={(e) => setGroupAction(e.target.value as 'delete' | 'merge' | '')}
                        style={{
                          padding: '2px 4px',
                          'font-size': '11px',
                          border: '1px solid #ddd',
                          'border-radius': '3px'
                        }}
                      >
                        <option value="">Действие</option>
                        <option value="delete">Удалить</option>
                        <option value="merge">Слить</option>
                      </select>
                      <button
                        onClick={executeGroupAction}
                        disabled={!groupAction()}
                        style={{
                          padding: '2px 6px',
                          'font-size': '11px',
                          background: groupAction() ? '#007bff' : '#ccc',
                          color: 'white',
                          border: 'none',
                          'border-radius': '3px',
                          cursor: groupAction() ? 'pointer' : 'not-allowed'
                        }}
                      >
                        ✓
                      </button>
                    </div>
                  </Show>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <For each={renderTopics(topics())}>{(row) => row}</For>
          </tbody>
        </table>
      </Show>

      {/* Модальное окно создания */}
      <TopicEditModal
        isOpen={createModal().show}
        topic={null}
        onClose={() => setCreateModal({ show: false })}
        onSave={createTopic}
      />

      {/* Модальное окно редактирования */}
      <TopicEditModal
        isOpen={editModal().show}
        topic={editModal().topic}
        onClose={() => setEditModal({ show: false, topic: null })}
        onSave={updateTopic}
      />

      {/* Модальное окно подтверждения удаления */}
      <Modal
        isOpen={deleteModal().show}
        onClose={() => setDeleteModal({ show: false, topic: null })}
        title="Подтверждение удаления"
      >
        <div>
          <Show when={selectedTopics().length > 1}>
            <p>
              Вы уверены, что хотите удалить <strong>{selectedTopics().length}</strong> выбранных тем?
            </p>
            <p class={styles['warning-text']}>
              Это действие нельзя отменить. Все дочерние топики также будут удалены.
            </p>
            <div class={styles['modal-actions']}>
              <Button variant="secondary" onClick={() => setDeleteModal({ show: false, topic: null })}>
                Отмена
              </Button>
              <Button variant="danger" onClick={deleteSelectedTopics}>
                Удалить {selectedTopics().length} тем
              </Button>
            </div>
          </Show>
          <Show when={selectedTopics().length <= 1}>
            <p>
              Вы уверены, что хотите удалить топик "<strong>{deleteModal().topic?.title}</strong>"?
            </p>
            <p class={styles['warning-text']}>
              Это действие нельзя отменить. Все дочерние топики также будут удалены.
            </p>
            <div class={styles['modal-actions']}>
              <Button variant="secondary" onClick={() => setDeleteModal({ show: false, topic: null })}>
                Отмена
              </Button>
                          <Button
              variant="danger"
              onClick={() => {
                if (deleteModal().topic) {
                  void deleteTopic(deleteModal().topic!.id)
                }
              }}
            >
              Удалить
            </Button>
            </div>
          </Show>
        </div>
      </Modal>

      {/* Модальное окно слияния тем */}
      <TopicMergeModal
        isOpen={mergeModal().show}
        onClose={() => {
          setMergeModal({ show: false })
          setSelectedTopics([])
          setGroupAction('')
        }}
        topics={rawTopics().filter(topic => selectedTopics().includes(topic.id))}
        onSuccess={(message) => {
          props.onSuccess(message)
          setSelectedTopics([])
          setGroupAction('')
          void loadTopics()
        }}
        onError={props.onError}
      />

      {/* Модальное окно назначения родителя */}
      <TopicSimpleParentModal
        isOpen={simpleParentModal().show}
        onClose={() => setSimpleParentModal({ show: false, topic: null })}
        topic={simpleParentModal().topic}
        allTopics={rawTopics()}
        onSuccess={(message) => {
          props.onSuccess(message)
          setSimpleParentModal({ show: false, topic: null })
          void loadTopics() // Перезагружаем данные
        }}
        onError={props.onError}
      />
    </div>
  )
}

export default TopicsRoute
