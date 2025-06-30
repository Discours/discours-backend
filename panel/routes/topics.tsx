/**
 * Компонент управления топиками
 * @module TopicsRoute
 */

import { Component, createEffect, createSignal, For, JSX, on, onMount, Show, untrack } from 'solid-js'
import { query } from '../graphql'
import type { Query } from '../graphql/generated/schema'
import { DELETE_TOPIC_MUTATION, UPDATE_TOPIC_MUTATION } from '../graphql/mutations'
import { GET_TOPICS_QUERY } from '../graphql/queries'
import TopicEditModal from '../modals/TopicEditModal'
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
      result.push(
        <tr
          onClick={() => setEditModal({ show: true, topic })}
          style={{ cursor: 'pointer' }}
          class={styles['clickable-row']}
        >
          <td>{topic.id}</td>
          <td style={{ 'padding-left': `${(topic.level || 0) * 20}px` }}>
            {topic.level! > 0 && '└─ '}
            {topic.title}
          </td>
          <td>{topic.slug}</td>
          <td>
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
          <td>{topic.community}</td>
          <td>{topic.parent_ids?.join(', ') || '—'}</td>
          <td onClick={(e) => e.stopPropagation()}>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setDeleteModal({ show: true, topic })
              }}
              class={styles['delete-button']}
              title="Удалить топик"
              aria-label="Удалить топик"
            >
              ×
            </button>
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
        <h2>Управление топиками</h2>
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
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <For each={renderTopics(topics())}>{(row) => row}</For>
          </tbody>
        </table>
      </Show>

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
              onClick={() => deleteModal().topic && deleteTopic(deleteModal().topic!.id)}
            >
              Удалить
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default TopicsRoute
