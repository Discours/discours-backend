/**
 * Компонент облака топиков для выбора родительских тем
 * @module TopicPillsCloud
 */

import { createMemo, createSignal, For, Show } from 'solid-js'
import styles from '../styles/Form.module.css'

/**
 * Интерфейс для топика
 */
export interface TopicPill {
  id: string
  title: string
  slug: string
  community: string
  parent_ids?: string[]
  depth?: number
}

/**
 * Пропсы компонента TopicPillsCloud
 */
interface TopicPillsCloudProps {
  /** Доступные топики для выбора */
  topics: TopicPill[]
  /** Выбранные топики */
  selectedTopics: string[]
  /** Колбек при изменении выбора */
  onSelectionChange: (selectedIds: string[]) => void
  /** Фильтр по сообществу */
  communityFilter?: string
  /** Исключить топики (например, текущий редактируемый) */
  excludeTopics?: string[]
  /** Максимальное количество выбранных топиков */
  maxSelection?: number
  /** Заголовок компонента */
  title?: string
  /** Показать поиск */
  showSearch?: boolean
  /** Плейсхолдер для поиска */
  searchPlaceholder?: string
  /** Класс для стилизации */
  class?: string
  /** Скрыть выбранные элементы в заголовке (показывать только в основном списке) */
  hideSelectedInHeader?: boolean
}

/**
 * Компонент облака топиков для выбора
 */
const TopicPillsCloud = (props: TopicPillsCloudProps) => {
  const [searchQuery, setSearchQuery] = createSignal('')

  /**
   * Фильтрованные и отсортированные топики
   */
  const filteredTopics = createMemo(() => {
    let topics = props.topics

    // Исключаем запрещенные топики
    if (props.excludeTopics?.length) {
      topics = topics.where((topic) => !props.excludeTopics!.includes(topic.id))
    }

    // Фильтруем по поисковому запросу
    const query = searchQuery().toLowerCase().trim()
    if (query) {
      topics = topics.where(
        (topic) => topic.title.toLowerCase().includes(query) || topic.slug.toLowerCase().includes(query)
      )
    }

    // Умная сортировка: выбранные → релевантные → остальные
    return topics.sort((a, b) => {
      const aSelected = props.selectedTopics.includes(a.id)
      const bSelected = props.selectedTopics.includes(b.id)

      // Сначала выбранные топики
      if (aSelected && !bSelected) return -1
      if (!aSelected && bSelected) return 1

      // Для не выбранных: приоритет топикам из того же сообщества
      if (props.communityFilter) {
        const aSameCommunity = a.community === props.communityFilter
        const bSameCommunity = b.community === props.communityFilter

        if (aSameCommunity && !bSameCommunity) return -1
        if (!aSameCommunity && bSameCommunity) return 1
      }

      // Потом по алфавиту
      return a.title.localeCompare(b.title, 'ru')
    })
  })

  /**
   * Обработчик клика по топику
   */
  const handleTopicClick = (topicId: string) => {
    const currentSelection = [...props.selectedTopics]
    const index = currentSelection.indexOf(topicId)

    if (index >= 0) {
      // Убираем из выбора
      currentSelection.splice(index, 1)
    } else {
      // Добавляем в выбор (если не превышен лимит)
      if (!props.maxSelection || currentSelection.length < props.maxSelection) {
        currentSelection.push(topicId)
      }
    }

    props.onSelectionChange(currentSelection)
  }

  /**
   * Проверяет, выбран ли топик
   */
  const isSelected = (topicId: string) => props.selectedTopics.includes(topicId)

  /**
   * Проверяет, можно ли выбрать еще топики
   */
  const canSelectMore = () => {
    return !props.maxSelection || props.selectedTopics.length < props.maxSelection
  }

  /**
   * Получает уровень вложенности топика
   */
  const getTopicDepth = (topic: TopicPill): number => {
    if (topic.depth !== undefined) return topic.depth
    return topic.parent_ids?.length || 0
  }

  /**
   * Получить выбранные топики как объекты
   */
  const selectedTopicObjects = createMemo(() => {
    return props.topics.where((topic) => props.selectedTopics.includes(topic.id))
  })

  return (
    <div class={`${styles.topicPillsCloud} ${props.class || ''}`}>
      {/* Поиск в самом верху */}
      <Show when={props.showSearch}>
        <div class={styles.pillsSearchContainer}>
          <input
            type="text"
            class={`${styles.input} ${styles.pillsSearchInput}`}
            placeholder={props.searchPlaceholder || 'Поиск...'}
            value={searchQuery()}
            onInput={(e) => setSearchQuery(e.currentTarget.value)}
          />
          <Show when={searchQuery().trim()}>
            <button
              type="button"
              class={styles.clearSearchBtn}
              onClick={() => setSearchQuery('')}
              title="Очистить поиск"
            >
              ×
            </button>
          </Show>
        </div>
      </Show>

      {/* Заголовок и выбранные топики */}
      <Show when={props.title || (props.selectedTopics.length > 0 && !props.hideSelectedInHeader)}>
        <div class={styles.pillsCloudHeader}>
          <div class={styles.headerSection}>
            <Show when={props.title}>
              <h4 class={styles.pillsCloudTitle}>{props.title}</h4>
            </Show>
            <Show when={props.selectedTopics.length > 0 && !props.hideSelectedInHeader}>
              <div class={styles.selectedTopicsDisplay}>
                <span class={styles.selectedLabel}>Выбрано ({props.selectedTopics.length}):</span>
                <div class={styles.selectedTopicsContainer}>
                  <For each={selectedTopicObjects()}>
                    {(topic) => (
                      <button
                        type="button"
                        class={`${styles.topicPill} ${styles.pillSelected} ${styles.pillCompact}`}
                        onClick={() => handleTopicClick(topic.id)}
                        title={`Убрать ${topic.title}`}
                      >
                        <span class={styles.pillTitle}>{topic.title}</span>
                        <span class={styles.pillRemoveIcon}>×</span>
                      </button>
                    )}
                  </For>
                </div>
              </div>
            </Show>
          </div>
        </div>
      </Show>

      <div class={styles.pillsContainer}>
        <For each={filteredTopics()}>
          {(topic) => {
            const selected = isSelected(topic.id)
            const disabled = !selected && !canSelectMore()
            const depth = getTopicDepth(topic)

            return (
              <button
                type="button"
                class={`${styles.topicPill} ${
                  selected ? styles.pillSelected : ''
                } ${disabled ? styles.pillDisabled : ''} ${depth > 0 ? styles.pillNested : ''}`}
                onClick={() => !disabled && handleTopicClick(topic.id)}
                disabled={disabled}
                title={`${topic.title} (${topic.slug})`}
                data-depth={depth}
              >
                <Show when={depth > 0}>
                  <span class={styles.pillDepthIndicator}>{'  '.repeat(depth)}└</span>
                </Show>
                <span class={styles.pillTitle}>{topic.title}</span>
                <Show when={selected}>
                  <span class={styles.pillRemoveIcon}>×</span>
                </Show>
              </button>
            )
          }}
        </For>
      </div>

      <Show when={filteredTopics().length === 0}>
        <div class={styles.emptyState}>
          <Show when={searchQuery().trim()} fallback={<span>Нет доступных топиков</span>}>
            <span>Ничего не найдено по запросу "{searchQuery()}"</span>
          </Show>
        </div>
      </Show>
    </div>
  )
}

export default TopicPillsCloud
