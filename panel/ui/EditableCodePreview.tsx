import { createEffect, createMemo, createSignal, Show } from 'solid-js'
import 'prismjs/themes/prism-tomorrow.css'

import styles from '../styles/CodePreview.module.css'
import {
  DEFAULT_EDITOR_CONFIG,
  detectLanguage,
  formatCode,
  handleTabKey,
  highlightCode
} from '../utils/codeHelpers'

interface EditableCodePreviewProps {
  content: string
  onContentChange: (newContent: string) => void
  onSave?: (content: string) => void
  onCancel?: () => void
  language?: string
  maxHeight?: string
  placeholder?: string
  showButtons?: boolean
  autoFormat?: boolean
  readOnly?: boolean
  theme?: 'dark' | 'light' | 'highContrast'
}

/**
 * Современный редактор кода с подсветкой синтаксиса и удобными возможностями редактирования
 *
 * Возможности:
 * - Подсветка синтаксиса в реальном времени
 * - Номера строк с синхронизацией скролла
 * - Автоформатирование кода
 * - Горячие клавиши (Ctrl+Enter для сохранения, Esc для отмены)
 * - Обработка Tab для отступов
 * - Сохранение позиции курсора
 * - Адаптивный дизайн
 * - Поддержка тем оформления
 */
const EditableCodePreview = (props: EditableCodePreviewProps) => {
  // Состояние компонента
  const [isEditing, setIsEditing] = createSignal(false)
  const [content, setContent] = createSignal(props.content)
  const [isSaving, setIsSaving] = createSignal(false)
  const [hasChanges, setHasChanges] = createSignal(false)

  // Ссылки на DOM элементы
  let editorRef: HTMLTextAreaElement | undefined
  let highlightRef: HTMLPreElement | undefined
  let lineNumbersRef: HTMLDivElement | undefined

  // Реактивные вычисления
  const language = createMemo(() => props.language || detectLanguage(content()))

  // Контент для отображения (отформатированный в режиме просмотра, исходный в режиме редактирования)
  const displayContent = createMemo(() => {
    if (isEditing()) {
      return content() // В режиме редактирования показываем исходный код
    }
    return props.autoFormat ? formatCode(content(), language()) : content() // В режиме просмотра - форматированный
  })

  const isEmpty = createMemo(() => !content()?.trim())
  const status = createMemo(() => {
    if (isSaving()) return 'saving'
    if (isEditing()) return 'editing'
    return 'idle'
  })

  /**
   * Синхронизирует скролл подсветки синтаксиса с textarea
   */
  const syncScroll = () => {
    if (!editorRef) return

    const scrollTop = editorRef.scrollTop
    const scrollLeft = editorRef.scrollLeft

    // Синхронизируем только подсветку синтаксиса в режиме редактирования
    if (highlightRef && isEditing()) {
      highlightRef.scrollTop = scrollTop
      highlightRef.scrollLeft = scrollLeft
    }
  }

  /**
   * Генерирует элементы номеров строк для CSS счетчика
   */
  const generateLineElements = createMemo(() => {
    const lines = displayContent().split('\n')
    return lines.map((_, _index) => <div class={styles.lineNumberItem} />)
  })

  /**
   * Обработчик изменения контента
   */
  const handleInput = (e: Event) => {
    const target = e.target as HTMLTextAreaElement
    const newContent = target.value

    setContent(newContent)
    setHasChanges(newContent !== props.content)
    props.onContentChange(newContent)
  }

  /**
   * Обработчик горячих клавиш
   */
  const handleKeyDown = (e: KeyboardEvent) => {
    // Ctrl+Enter или Cmd+Enter для сохранения
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      void handleSave()
      return
    }

    // Escape для отмены
    if (e.key === 'Escape') {
      e.preventDefault()
      handleCancel()
      return
    }

    // Ctrl+Shift+F для форматирования
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'f') {
      e.preventDefault()
      handleFormat()
      return
    }

    // Tab для отступов
    if (handleTabKey(e)) {
      // Обновляем контент после вставки отступа
      setTimeout(() => {
        const _target = e.target as HTMLTextAreaElement
        handleInput(e)
      }, 0)
    }
  }

  /**
   * Форматирование кода
   */
  const handleFormat = () => {
    if (!props.autoFormat) return

    const formatted = formatCode(content(), language())
    if (formatted !== content()) {
      setContent(formatted)
      setHasChanges(true)
      props.onContentChange(formatted)

      // Обновляем textarea
      if (editorRef) {
        editorRef.value = formatted
      }
    }
  }

  /**
   * Сохранение изменений
   */
  const handleSave = async () => {
    if (!props.onSave || isSaving()) return

    setIsSaving(true)
    try {
      await props.onSave(content())
      setHasChanges(false)
      setIsEditing(false)
    } catch (error) {
      console.error('Ошибка при сохранении:', error)
    } finally {
      setIsSaving(false)
    }
  }

  /**
   * Отмена изменений
   */
  const handleCancel = () => {
    const originalContent = props.content
    setContent(originalContent)
    setHasChanges(false)

    // Обновляем textarea
    if (editorRef) {
      editorRef.value = originalContent
    }

    if (props.onCancel) {
      props.onCancel()
    }
    setIsEditing(false)
  }

  /**
   * Переход в режим редактирования
   */
  const startEditing = () => {
    if (props.readOnly) return

    // Форматируем контент при переходе в режим редактирования, если автоформатирование включено
    if (props.autoFormat) {
      const formatted = formatCode(content(), language())
      if (formatted !== content()) {
        setContent(formatted)
        props.onContentChange(formatted)
      }
    }

    setIsEditing(true)

    // Фокус на editor после рендера
    setTimeout(() => {
      if (editorRef) {
        editorRef.focus()
        // Устанавливаем курсор в конец
        editorRef.setSelectionRange(editorRef.value.length, editorRef.value.length)
      }
    }, 50)
  }

  // Эффект для обновления контента при изменении props
  createEffect(() => {
    if (!isEditing()) {
      setContent(props.content)
      setHasChanges(false)
    }
  })

  // Эффект для синхронизации textarea с content
  createEffect(() => {
    if (editorRef && editorRef.value !== content()) {
      editorRef.value = content()
    }
  })

  return (
    <div class={`${styles.editableCodeContainer} ${styles[props.theme || 'darkTheme']}`}>
      {/* Основной контейнер редактора */}
      <div class={`${styles.editorContainer} ${isEditing() ? styles.editing : ''}`}>
        {/* Область кода */}
        <div class={styles.codeArea}>
          {/* Контейнер для кода со скроллом */}
          <div class={styles.codeContentWrapper}>
            {/* Контейнер для самого кода */}
            <div class={styles.codeTextWrapper}>
              {/* Нумерация строк внутри скроллящегося контейнера */}
              <div ref={lineNumbersRef} class={styles.lineNumbers}>
                {generateLineElements()}
              </div>
              {/* Подсветка синтаксиса в режиме редактирования */}
              <Show when={isEditing()}>
                <pre
                  ref={highlightRef}
                  class={styles.syntaxHighlight}
                  aria-hidden="true"
                  innerHTML={highlightCode(displayContent(), language())}
                />
              </Show>

              {/* Режим просмотра или редактирования */}
              <Show
                when={isEditing()}
                fallback={
                  <Show
                    when={!isEmpty()}
                    fallback={
                      <div class={styles.placeholderClickable} onClick={startEditing}>
                        {props.placeholder || 'Нажмите для редактирования...'}
                      </div>
                    }
                  >
                    <pre
                      class={styles.codePreviewContent}
                      onClick={startEditing}
                      innerHTML={highlightCode(displayContent(), language())}
                    />
                  </Show>
                }
              >
                <textarea
                  ref={editorRef}
                  class={styles.editorTextarea}
                  value={content()}
                  onInput={handleInput}
                  onKeyDown={handleKeyDown}
                  onScroll={syncScroll}
                  placeholder={props.placeholder || 'Введите код...'}
                  spellcheck={false}
                  autocomplete="off"
                  autocorrect="off"
                  autocapitalize="off"
                  wrap="off"
                  style={`
                    font-family: ${DEFAULT_EDITOR_CONFIG.fontFamily};
                    font-size: ${DEFAULT_EDITOR_CONFIG.fontSize}px;
                    line-height: ${DEFAULT_EDITOR_CONFIG.lineHeight};
                    tab-size: ${DEFAULT_EDITOR_CONFIG.tabSize};
                    background: transparent;
                    color: transparent;
                    caret-color: var(--code-text);
                  `}
                />
              </Show>
            </div>
          </div>
        </div>
      </div>

      {/* Панель управления */}
      <div class={styles.controls}>
        {/* Левая часть - информация */}
        <div class={styles.controlsLeft}>
          <span class={styles.languageBadge}>{language()}</span>

          <div class={styles.statusIndicator}>
            <div class={`${styles.statusDot} ${styles[status()]}`} />
            <span>
              {status() === 'saving' && 'Сохранение...'}
              {status() === 'editing' && 'Редактирование'}
              {status() === 'idle' && (hasChanges() ? 'Есть изменения' : 'Сохранено')}
            </span>
          </div>

          <Show when={hasChanges()}>
            <span style="color: var(--code-warning); font-size: 11px;">●</span>
          </Show>
        </div>

        {/* Правая часть - кнопки */}
        <Show when={props.showButtons !== false}>
          <div class={styles.controlsRight}>
            <Show
              when={!isEditing()}
              fallback={
                <div class={`${styles.editingControls} ${styles.fadeIn}`}>
                  <Show when={props.autoFormat}>
                    <button
                      class={styles.formatButton}
                      onClick={handleFormat}
                      disabled={isSaving()}
                      title="Форматировать код (Ctrl+Shift+F)"
                    >
                      🎨 Форматировать
                    </button>
                  </Show>

                  <button
                    class={styles.saveButton}
                    onClick={handleSave}
                    disabled={isSaving() || !hasChanges()}
                    title="Сохранить изменения (Ctrl+Enter)"
                  >
                    {isSaving() ? '⏳ Сохранение...' : '💾 Сохранить'}
                  </button>

                  <button
                    class={styles.cancelButton}
                    onClick={handleCancel}
                    disabled={isSaving()}
                    title="Отменить изменения (Esc)"
                  >
                    ❌ Отмена
                  </button>
                </div>
              }
            >
              <Show when={!props.readOnly}>
                <button class={styles.editButton} onClick={startEditing} title="Редактировать код">
                  ✏️ Редактировать
                </button>
              </Show>
            </Show>
          </div>
        </Show>
      </div>
    </div>
  )
}

export default EditableCodePreview
