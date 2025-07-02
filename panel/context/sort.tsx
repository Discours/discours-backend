import { createContext, createSignal, ParentComponent, useContext } from 'solid-js'

/**
 * Типы полей сортировки для разных вкладок
 */
export type AuthorsSortField = 'id' | 'email' | 'name' | 'created_at' | 'last_seen'
export type ShoutsSortField = 'id' | 'title' | 'slug' | 'created_at' | 'published_at' | 'updated_at'
export type TopicsSortField =
  | 'id'
  | 'title'
  | 'slug'
  | 'created_at'
  | 'authors'
  | 'shouts'
  | 'followers'
  | 'authors'
export type CommunitiesSortField =
  | 'id'
  | 'name'
  | 'slug'
  | 'created_at'
  | 'created_by'
  | 'shouts'
  | 'followers'
  | 'authors'
export type CollectionsSortField = 'id' | 'title' | 'slug' | 'created_at' | 'published_at'
export type InvitesSortField = 'inviter_name' | 'author_name' | 'shout_title' | 'status'

/**
 * Общий тип для всех полей сортировки
 */
export type SortField =
  | AuthorsSortField
  | ShoutsSortField
  | TopicsSortField
  | CommunitiesSortField
  | CollectionsSortField
  | InvitesSortField

/**
 * Направление сортировки
 */
export type SortDirection = 'asc' | 'desc'

/**
 * Состояние сортировки
 */
export interface SortState {
  field: SortField
  direction: SortDirection
}

/**
 * Конфигурация сортировки для разных вкладок
 */
export interface TabSortConfig {
  allowedFields: SortField[]
  defaultField: SortField
  defaultDirection: SortDirection
}

/**
 * Контекст для управления сортировкой таблиц
 */
interface TableSortContextType {
  sortState: () => SortState
  setSortState: (state: SortState) => void
  handleSort: (field: SortField, allowedFields?: SortField[]) => void
  getSortIcon: (field: SortField) => string
  isFieldAllowed: (field: SortField, allowedFields?: SortField[]) => boolean
}

/**
 * Создаем контекст
 */
const TableSortContext = createContext<TableSortContextType>()

/**
 * Провайдер контекста сортировки
 */
export const TableSortProvider: ParentComponent = (props) => {
  // Состояние сортировки - по умолчанию сортировка по ID по возрастанию
  const [sortState, setSortState] = createSignal<SortState>({
    field: 'id',
    direction: 'asc'
  })

  /**
   * Проверяет, разрешено ли поле для сортировки
   */
  const isFieldAllowed = (field: SortField, allowedFields?: SortField[]) => {
    if (!allowedFields) return true
    return allowedFields.includes(field)
  }

  /**
   * Обработчик клика по заголовку колонки для сортировки
   */
  const handleSort = (field: SortField, allowedFields?: SortField[]) => {
    // Проверяем, разрешено ли поле для сортировки
    if (!isFieldAllowed(field, allowedFields)) {
      console.warn(`Поле ${field} не разрешено для сортировки`)
      return
    }

    const current = sortState()
    let newDirection: SortDirection = 'asc'

    if (current.field === field) {
      // Если кликнули по той же колонке, меняем направление
      newDirection = current.direction === 'asc' ? 'desc' : 'asc'
    }

    const newState = { field, direction: newDirection }
    console.log('Изменение сортировки:', { from: current, to: newState })
    setSortState(newState)
  }

  /**
   * Получает иконку сортировки для колонки
   */
  const getSortIcon = (field: SortField) => {
    const current = sortState()
    if (current.field !== field) {
      return '⇅' // Неактивная сортировка
    }
    return current.direction === 'asc' ? '▲' : '▼'
  }

  const contextValue: TableSortContextType = {
    sortState,
    setSortState,
    handleSort,
    getSortIcon,
    isFieldAllowed
  }

  return <TableSortContext.Provider value={contextValue}>{props.children}</TableSortContext.Provider>
}

/**
 * Хук для использования контекста сортировки
 */
export const useTableSort = () => {
  const context = useContext(TableSortContext)
  if (!context) {
    throw new Error('useTableSort должен использоваться внутри TableSortProvider')
  }
  return context
}
