import { For } from 'solid-js'
import styles from '../styles/Pagination.module.css'

interface PaginationProps {
  currentPage: number
  totalPages: number
  total: number
  limit: number
  onPageChange: (page: number) => void
  onPerPageChange?: (limit: number) => void
  perPageOptions?: number[]
}

const Pagination = (props: PaginationProps) => {
  const perPageOptions = props.perPageOptions || [20, 50, 100, 200]

  // Генерируем массив страниц для отображения
  const pages = () => {
    const result: (number | string)[] = []
    const maxVisiblePages = 5 // Максимальное количество видимых страниц

    // Всегда показываем первую страницу
    result.push(1)

    // Вычисляем диапазон страниц вокруг текущей
    let startPage = Math.max(2, props.currentPage - Math.floor(maxVisiblePages / 2))
    const endPage = Math.min(props.totalPages - 1, startPage + maxVisiblePages - 2)

    // Корректируем диапазон, если он выходит за границы
    if (endPage - startPage < maxVisiblePages - 2) {
      startPage = Math.max(2, endPage - maxVisiblePages + 2)
    }

    // Добавляем многоточие после первой страницы, если нужно
    if (startPage > 2) {
      result.push('...')
    }

    // Добавляем страницы из диапазона
    for (let i = startPage; i <= endPage; i++) {
      result.push(i)
    }

    // Добавляем многоточие перед последней страницей, если нужно
    if (endPage < props.totalPages - 1) {
      result.push('...')
    }

    // Всегда показываем последнюю страницу, если есть больше одной страницы
    if (props.totalPages > 1) {
      result.push(props.totalPages)
    }

    return result
  }

  const startIndex = () => (props.currentPage - 1) * props.limit + 1
  const endIndex = () => Math.min(props.currentPage * props.limit, props.total)

  return (
    <div class={styles.pagination}>
      <div class={styles['pagination-info']}>
        Показано {startIndex()} - {endIndex()} из {props.total}
      </div>

      <div class={styles['pagination-controls']}>
        <button
          class={styles.pageButton}
          onClick={() => props.onPageChange(props.currentPage - 1)}
          disabled={props.currentPage === 1}
        >
          ←
        </button>

        <For each={pages()}>
          {(page) => (
            <>
              {page === '...' ? (
                <span class={styles['pagination-ellipsis']}>...</span>
              ) : (
                <button
                  class={`${styles.pageButton} ${page === props.currentPage ? styles.currentPage : ''}`}
                  onClick={() => props.onPageChange(Number(page))}
                >
                  {page}
                </button>
              )}
            </>
          )}
        </For>

        <button
          class={styles.pageButton}
          onClick={() => props.onPageChange(props.currentPage + 1)}
          disabled={props.currentPage === props.totalPages}
        >
          →
        </button>
      </div>

      {props.onPerPageChange && (
        <div class={styles['pagination-per-page']}>
          На странице:
          <select
            class={styles.perPageSelect}
            value={props.limit}
            onChange={(e) => props.onPerPageChange!(Number(e.target.value))}
          >
            <For each={perPageOptions}>{(option) => <option value={option}>{option}</option>}</For>
          </select>
        </div>
      )}
    </div>
  )
}

export default Pagination
