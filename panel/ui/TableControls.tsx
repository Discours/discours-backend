import { JSX, Show } from 'solid-js'
import styles from '../styles/Table.module.css'

export interface TableControlsProps {
  onRefresh?: () => void
  isLoading?: boolean
  children?: JSX.Element
  actions?: JSX.Element
  searchValue?: string
  onSearchChange?: (value: string) => void
  onSearch?: () => void
  searchPlaceholder?: string
}

/**
 * Компонент для унифицированного управления таблицами
 * Содержит элементы управления сортировкой, фильтрацией и действиями
 */
const TableControls = (props: TableControlsProps) => {
  return (
    <div class={styles.tableControls}>
      <div class={styles.controlsContainer}>
        {/* Поиск и действия в одной строке */}
        <Show when={props.onSearchChange}>
          <div class={styles.searchContainer}>
            <input
              type="text"
              placeholder={props.searchPlaceholder}
              value={props.searchValue || ''}
              onInput={(e) => props.onSearchChange?.(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && props.onSearch) {
                  props.onSearch()
                }
              }}
              class={styles.searchInput}
            />
            <Show when={props.onSearch}>
              <button class={styles.searchButton} onClick={props.onSearch}>
                Поиск
              </button>
            </Show>
          </div>
        </Show>

        {/* Действия справа от поиска */}
        <Show when={props.actions}>
          <div class={styles.controlsRight}>{props.actions}</div>
        </Show>

        {/* Дополнительные элементы управления */}
        {props.children}
      </div>
    </div>
  )
}

export default TableControls
