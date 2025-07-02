import { createSignal, For, JSX, Show } from 'solid-js'
import styles from '../styles/Form.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'

// Типы для топиков
interface Topic {
  id: number
  title: string
  slug: string
  parent_ids?: number[]
  children?: Topic[]
  level?: number
  community: number
}

interface TopicHierarchyModalProps {
  isOpen: boolean
  onClose: () => void
  topics: Topic[]
  onSave: (hierarchyChanges: HierarchyChange[]) => void
  onError: (error: string) => void
}

interface HierarchyChange {
  topicId: number
  newParentIds: number[]
  oldParentIds: number[]
}

const TopicHierarchyModal = (props: TopicHierarchyModalProps) => {
  const [localTopics, setLocalTopics] = createSignal<Topic[]>([])
  const [changes, setChanges] = createSignal<HierarchyChange[]>([])
  const [expandedNodes, setExpandedNodes] = createSignal<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = createSignal('')
  const [selectedForMove, setSelectedForMove] = createSignal<number | null>(null)

  // Инициализация локального состояния
  const initializeTopics = () => {
    const hierarchicalTopics = buildHierarchy(props.topics)
    setLocalTopics(hierarchicalTopics)
    setChanges([])
    setSearchQuery('')
    setSelectedForMove(null)
    // Раскрываем все узлы по умолчанию
    const allIds = new Set(props.topics.map((t) => t.id))
    setExpandedNodes(allIds)
  }

  // Построение иерархической структуры
  const buildHierarchy = (flatTopics: Topic[]): Topic[] => {
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
        rootTopics.push(currentTopic)
      } else {
        const parentId = topic.parent_ids[topic.parent_ids.length - 1]
        const parent = topicMap.get(parentId)
        if (parent) {
          currentTopic.level = (parent.level || 0) + 1
          parent.children!.push(currentTopic)
        } else {
          rootTopics.push(currentTopic)
        }
      }
    })

    return rootTopics
  }

  // Функция удалена - используем кликабельный интерфейс вместо drag & drop

  // Проверка, является ли топик потомком другого
  const isDescendant = (parentId: number, childId: number): boolean => {
    const checkChildren = (topics: Topic[]): boolean => {
      for (const topic of topics) {
        if (topic.id === childId) return true
        if (topic.children && checkChildren(topic.children)) return true
      }
      return false
    }

    const parentTopic = findTopicById(parentId)
    return parentTopic ? checkChildren(parentTopic.children || []) : false
  }

  // Поиск топика по ID
  const findTopicById = (id: number): Topic | null => {
    const search = (topics: Topic[]): Topic | null => {
      for (const topic of topics) {
        if (topic.id === id) return topic
        if (topic.children) {
          const found = search(topic.children)
          if (found) return found
        }
      }
      return null
    }
    return search(localTopics())
  }

  // Обновление родителя топика
  const updateTopicParent = (topicId: number, newParentIds: number[]) => {
    const flatTopics = flattenTopics(localTopics())
    const updatedTopics = flatTopics.map((topic) =>
      topic.id === topicId ? { ...topic, parent_ids: newParentIds } : topic
    )
    const newHierarchy = buildHierarchy(updatedTopics)
    setLocalTopics(newHierarchy)
  }

  // Преобразование дерева в плоский список
  const flattenTopics = (topics: Topic[]): Topic[] => {
    const result: Topic[] = []
    const flatten = (topicList: Topic[]) => {
      topicList.forEach((topic) => {
        result.push(topic)
        if (topic.children) {
          flatten(topic.children)
        }
      })
    }
    flatten(topics)
    return result
  }

  // Переключение раскрытия узла
  const toggleExpanded = (topicId: number) => {
    const expanded = expandedNodes()
    if (expanded.has(topicId)) {
      expanded.delete(topicId)
    } else {
      expanded.add(topicId)
    }
    setExpandedNodes(new Set(expanded))
  }

  // Поиск темы по названию
  const findTopicByTitle = (title: string): Topic | null => {
    const query = title.toLowerCase().trim()
    if (!query) return null

    const search = (topics: Topic[]): Topic | null => {
      for (const topic of topics) {
        if (topic.title.toLowerCase().includes(query)) {
          return topic
        }
        if (topic.children) {
          const found = search(topic.children)
          if (found) return found
        }
      }
      return null
    }

    return search(localTopics())
  }

  // Выбор темы для перемещения
  const selectTopicForMove = (topicId: number) => {
    setSelectedForMove(topicId)
    const topic = findTopicById(topicId)
    if (topic) {
      props.onError(
        `Выбрана тема "${topic.title}" для перемещения. Теперь нажмите на новую родительскую тему или используйте "Сделать корневой".`
      )
    }
  }

  // Перемещение выбранной темы к новому родителю
  const moveSelectedTopic = (newParentId: number | null) => {
    const selectedId = selectedForMove()
    if (!selectedId) return

    const selectedTopic = findTopicById(selectedId)
    if (!selectedTopic) return

    // Проверяем циклы
    if (newParentId && isDescendant(newParentId, selectedId)) {
      props.onError('Нельзя переместить тему в своего потомка')
      return
    }

    let newParentIds: number[] = []
    if (newParentId) {
      const newParent = findTopicById(newParentId)
      if (newParent) {
        newParentIds = [...(newParent.parent_ids || []), newParentId]
      }
    }

    // Обновляем локальное состояние
    updateTopicParent(selectedId, newParentIds)

    // Добавляем в список изменений
    setChanges((prev) => [
      ...prev.filter((c) => c.topicId !== selectedId),
      {
        topicId: selectedId,
        newParentIds,
        oldParentIds: selectedTopic.parent_ids || []
      }
    ])

    setSelectedForMove(null)
  }

  // Раскрытие пути до определенной темы
  const expandPathToTopic = (topicId: number) => {
    const topic = findTopicById(topicId)
    if (!topic || !topic.parent_ids) return

    const expanded = expandedNodes()
    // Раскрываем всех родителей
    topic.parent_ids.forEach((parentId) => {
      expanded.add(parentId)
    })
    setExpandedNodes(new Set(expanded))
  }

  // Рендеринг дерева топиков
  const renderTree = (topics: Topic[]): JSX.Element => {
    return (
      <For each={topics}>
        {(topic) => {
          const isExpanded = expandedNodes().has(topic.id)
          const isSelected = selectedForMove() === topic.id
          const isTarget = selectedForMove() && selectedForMove() !== topic.id
          const hasChildren = topic.children && topic.children.length > 0

          return (
            <div class={styles.treeNode}>
              <div
                class={`${styles.treeItem} ${isSelected ? styles.selectedForMove : ''} ${isTarget ? styles.moveTarget : ''}`}
                onClick={() => {
                  if (selectedForMove() && selectedForMove() !== topic.id) {
                    // Если уже выбрана тема для перемещения, делаем текущую тему родителем
                    moveSelectedTopic(topic.id)
                  } else {
                    // Иначе выбираем эту тему для перемещения
                    selectTopicForMove(topic.id)
                  }
                }}
                style={{
                  'padding-left': `${(topic.level || 0) * 20}px`,
                  cursor: 'pointer',
                  border: isSelected
                    ? '2px solid #007bff'
                    : isTarget
                      ? '2px dashed #28a745'
                      : '1px solid transparent',
                  'background-color': isSelected ? '#e3f2fd' : isTarget ? '#d4edda' : 'transparent'
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    'align-items': 'center',
                    gap: '8px'
                  }}
                >
                  <Show when={hasChildren}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleExpanded(topic.id)
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        'font-size': '12px'
                      }}
                    >
                      {isExpanded ? '▼' : '▶'}
                    </button>
                  </Show>
                  <Show when={!hasChildren}>
                    <span style={{ width: '12px' }} />
                  </Show>

                  <Show when={isSelected}>
                    <span class={styles.selectedIcon}>📦</span>
                  </Show>
                  <Show when={isTarget}>
                    <span class={styles.targetIcon}>📂</span>
                  </Show>
                  <Show when={!isSelected && !isTarget}>
                    <span class={styles.clickIcon}>#</span>
                  </Show>

                  <span class={styles.topicTitle}>{topic.title}</span>
                  <span class={styles.topicId}>#{topic.id}</span>
                </div>
              </div>

              <Show when={isExpanded && hasChildren}>
                <div class={styles.treeChildren}>{renderTree(topic.children!)}</div>
              </Show>
            </div>
          )
        }}
      </For>
    )
  }

  // Сохранение изменений
  const handleSave = () => {
    if (changes().length === 0) {
      props.onError('Нет изменений для сохранения')
      return
    }
    props.onSave(changes())
  }

  // Инициализация при открытии
  if (props.isOpen && localTopics().length === 0) {
    initializeTopics()
  }

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title="Управление иерархией тем" size="large">
      <div class={styles.hierarchyContainer}>
        <div class={styles.instructions}>
          <h4>Инструкции:</h4>
          <ul>
            <li>🔍 Найдите тему по названию или прокрутите список</li>
            <li># Нажмите на тему, чтобы выбрать её для перемещения (синяя рамка)</li>
            <li>📂 Нажмите на другую тему, чтобы сделать её родителем (зеленая рамка)</li>
            <li>🏠 Используйте кнопку "Сделать корневой" для перемещения на верхний уровень</li>
            <li>▶/▼ Раскрывайте/сворачивайте ветки дерева</li>
          </ul>
        </div>

        <div class={styles.searchSection}>
          <label class={styles.label}>Поиск темы:</label>
          <input
            type="text"
            value={searchQuery()}
            onInput={(e) => {
              const query = e.target.value
              setSearchQuery(query)
              // Автоматически находим и подсвечиваем тему
              if (query.trim()) {
                const foundTopic = findTopicByTitle(query)
                if (foundTopic) {
                  // Раскрываем путь до найденной темы
                  expandPathToTopic(foundTopic.id)
                }
              }
            }}
            placeholder="Введите название темы для поиска..."
            class={styles.searchInput}
          />
          <Show when={searchQuery() && findTopicByTitle(searchQuery())}>
            <div class={styles.searchResult}>
              ✅ Найдена тема: <strong>{findTopicByTitle(searchQuery())?.title}</strong>
            </div>
          </Show>
          <Show when={searchQuery() && !findTopicByTitle(searchQuery())}>
            <div class={styles.searchNoResult}>❌ Тема не найдена</div>
          </Show>
        </div>

        <div class={styles.hierarchyTree}>{renderTree(localTopics())}</div>

        <Show when={changes().length > 0}>
          <div class={styles.changesSummary}>
            <h4>Планируемые изменения ({changes().length}):</h4>
            <For each={changes()}>
              {(change) => {
                const topic = findTopicById(change.topicId)
                return (
                  <div class={styles.changeItem}>
                    <strong>{topic?.title}</strong>:{' '}
                    {change.newParentIds.length === 0
                      ? 'станет корневой темой'
                      : `переместится под тему #${change.newParentIds[change.newParentIds.length - 1]}`}
                  </div>
                )
              }}
            </For>
          </div>
        </Show>

        <Show when={selectedForMove()}>
          <div class={styles.actionZone}>
            <div class={styles.selectedTopicInfo}>
              <h4>Выбрана для перемещения:</h4>
              <div class={styles.selectedTopicDisplay}>
                📦 <strong>{findTopicById(selectedForMove()!)?.title}</strong> #{selectedForMove()}
              </div>
            </div>

            <div class={styles.actionButtons}>
              <button class={styles.rootButton} onClick={() => moveSelectedTopic(null)}>
                🏠 Сделать корневой темой
              </button>
              <button class={styles.cancelButton} onClick={() => setSelectedForMove(null)}>
                ❌ Отменить выбор
              </button>
            </div>
          </div>
        </Show>

        <div class={styles.modalActions}>
          <Button variant="secondary" onClick={props.onClose}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={changes().length === 0}>
            Сохранить изменения ({changes().length})
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default TopicHierarchyModal
