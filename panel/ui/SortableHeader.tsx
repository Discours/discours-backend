import { Component, JSX, Show } from 'solid-js'
import { SortField, useTableSort } from '../context/sort'
import { useI18n } from '../intl/i18n'
import styles from '../styles/Table.module.css'

/**
 * Свойства компонента SortableHeader
 */
interface SortableHeaderProps {
  field: SortField
  children: JSX.Element
  allowedFields?: SortField[]
  class?: string
}

/**
 * Компонент сортируемого заголовка таблицы
 * Отображает заголовок с возможностью сортировки при клике
 */
const SortableHeader: Component<SortableHeaderProps> = (props) => {
  const { handleSort, getSortIcon, sortState, isFieldAllowed } = useTableSort()
  const { tr } = useI18n()

  const isActive = () => sortState().field === props.field
  const isAllowed = () => isFieldAllowed(props.field, props.allowedFields)

  const handleClick = () => {
    if (isAllowed()) {
      handleSort(props.field, props.allowedFields)
    }
  }

  return (
    <th
      class={`${styles.sortableHeader} ${props.class || ''} ${!isAllowed() ? styles.disabledHeader : ''}`}
      data-active={isActive()}
      onClick={handleClick}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && isAllowed()) {
          e.preventDefault()
          handleClick()
        }
      }}
      tabindex={isAllowed() ? 0 : -1}
      data-sort={isActive() ? (sortState().direction === 'asc' ? 'ascending' : 'descending') : 'none'}
      style={{
        cursor: isAllowed() ? 'pointer' : 'not-allowed',
        opacity: isAllowed() ? 1 : 0.6
      }}
    >
      <span class={styles.headerContent}>
        {typeof props.children === 'string' ? tr(props.children as string) : props.children}
        <Show when={isAllowed()}>
          <span class={styles.sortIcon}>{getSortIcon(props.field)}</span>
        </Show>
      </span>
    </th>
  )
}

export default SortableHeader
