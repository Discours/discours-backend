import { Component, createEffect, createSignal } from 'solid-js'
import styles from '../styles/Modal.module.css'
import Button from '../ui/Button'
import HTMLEditor from '../ui/HTMLEditor'
import Modal from '../ui/Modal'

interface ReactionEditModalProps {
  reaction: {
    id: number
    kind: string
    body: string
    created_at: number
    updated_at?: number
    deleted_at?: number
    reply_to?: number
    created_by: {
      id: number
      name: string
      email: string
      slug: string
    }
    shout: {
      id: number
      title: string
      slug: string
      layout: string
      created_at: number
      published_at?: number
      deleted_at?: number
    }
    stat: {
      comments_count: number
      rating: number
    }
  }
  isOpen: boolean
  onClose: () => void
  onSave: (reaction: { id: number; body?: string; deleted_at?: number }) => Promise<void>
}

/**
 * Модальное окно для редактирования реакции
 */
const ReactionEditModal: Component<ReactionEditModalProps> = (props) => {
  const [body, setBody] = createSignal('')
  const [loading, setLoading] = createSignal(false)
  const [error, setError] = createSignal('')

  // Инициализация данных при изменении реакции
  createEffect(() => {
    if (props.reaction) {
      setBody(props.reaction.body || '')
      setError('')
    }
  })

  /**
   * Обработка сохранения изменений
   */
  async function handleSave() {
    try {
      setLoading(true)
      setError('')

      const updateData: { id: number; body?: string; deleted_at?: number } = {
        id: props.reaction.id,
        body: body()
      }

      await props.onSave(updateData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Получает название типа реакции на русском
   */
  const getReactionName = (kind: string): string => {
    switch (kind) {
      case 'LIKE':
        return 'Лайк'
      case 'DISLIKE':
        return 'Дизлайк'
      case 'COMMENT':
        return 'Комментарий'
      case 'QUOTE':
        return 'Цитата'
      case 'AGREE':
        return 'Согласен'
      case 'DISAGREE':
        return 'Не согласен'
      case 'ASK':
        return 'Вопрос'
      case 'PROPOSE':
        return 'Предложение'
      case 'PROOF':
        return 'Доказательство'
      case 'DISPROOF':
        return 'Опровержение'
      case 'ACCEPT':
        return 'Принять'
      case 'REJECT':
        return 'Отклонить'
      case 'CREDIT':
        return 'Упоминание'
      case 'SILENT':
        return 'Причастность'
      default:
        return kind
    }
  }

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title="Редактирование реакции">
      <div class={styles['modal-content']}>
        {error() && <div class={styles['error-message']}>{error()}</div>}

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>ID реакции:</label>
          <input type="text" value={props.reaction.id} disabled class={styles['form-input']} />
        </div>

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>Тип реакции:</label>
          <input
            type="text"
            value={getReactionName(props.reaction.kind)}
            disabled
            class={styles['form-input']}
          />
        </div>

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>Автор:</label>
          <input
            type="text"
            value={`${props.reaction.created_by.name || 'Без имени'} (${props.reaction.created_by.email})`}
            disabled
            class={styles['form-input']}
          />
        </div>

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>Публикация:</label>
          <input
            type="text"
            value={`${props.reaction.shout.title} (ID: ${props.reaction.shout.id})`}
            disabled
            class={styles['form-input']}
          />
        </div>

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>Текст реакции:</label>
          <HTMLEditor
            value={body()}
            onInput={(value) => setBody(value)}
            placeholder="Введите текст реакции (поддерживается HTML)..."
            rows={6}
          />
        </div>

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>Статистика:</label>
          <div class={styles['stat-info']}>
            <span>Рейтинг: {props.reaction.stat.rating}</span>
            <span>Комментариев: {props.reaction.stat.comments_count}</span>
          </div>
        </div>

        <div class={styles['form-group']}>
          <label class={styles['form-label']}>Статус:</label>
          <input
            type="text"
            value={props.reaction.deleted_at ? 'Удалено' : 'Активно'}
            disabled
            class={styles['form-input']}
          />
        </div>

        <div class={styles['modal-actions']}>
          <Button variant="secondary" onClick={props.onClose} disabled={loading()}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={loading()}>
            {loading() ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default ReactionEditModal
