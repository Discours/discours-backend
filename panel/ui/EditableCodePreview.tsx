import Prism from 'prismjs'
import { createEffect, createSignal, onMount, Show } from 'solid-js'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-markup'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-css'
import 'prismjs/themes/prism-tomorrow.css'

import styles from '../styles/CodePreview.module.css'
import { detectLanguage } from './CodePreview'

interface EditableCodePreviewProps {
  content: string
  onContentChange: (newContent: string) => void
  onSave?: (content: string) => void
  onCancel?: () => void
  language?: string
  maxHeight?: string
  placeholder?: string
  showButtons?: boolean
}

/**
 * Форматирует HTML контент для лучшего отображения
 * Убирает лишние пробелы и делает разметку красивой
 */
const formatHtmlContent = (html: string): string => {
  if (!html || typeof html !== 'string') return ''

  // Удаляем лишние пробелы между тегами
  const formatted = html
    .replace(/>\s+</g, '><') // Убираем пробелы между тегами
    .replace(/\s+/g, ' ') // Множественные пробелы в одиночные
    .trim() // Убираем пробелы в начале и конце

  // Добавляем отступы для лучшего отображения
  const indent = '  '
  let indentLevel = 0
  const lines: string[] = []

  // Разбиваем на токены (теги и текст)
  const tokens = formatted.match(/<[^>]+>|[^<]+/g) || []

  for (const token of tokens) {
    if (token.startsWith('<')) {
      if (token.startsWith('</')) {
        // Закрывающий тег - уменьшаем отступ
        indentLevel = Math.max(0, indentLevel - 1)
        lines.push(indent.repeat(indentLevel) + token)
      } else if (token.endsWith('/>')) {
        // Самозакрывающийся тег
        lines.push(indent.repeat(indentLevel) + token)
      } else {
        // Открывающий тег - добавляем отступ
        lines.push(indent.repeat(indentLevel) + token)
        indentLevel++
      }
    } else {
      // Текстовое содержимое
      const trimmed = token.trim()
      if (trimmed) {
        lines.push(indent.repeat(indentLevel) + trimmed)
      }
    }
  }

  return lines.join('\n')
}

/**
 * Генерирует номера строк для текста
 */
const generateLineNumbers = (text: string): string[] => {
  if (!text) return ['1']
  const lines = text.split('\n')
  return lines.map((_, index) => String(index + 1))
}

/**
 * Редактируемый компонент для кода с подсветкой синтаксиса
 */
const EditableCodePreview = (props: EditableCodePreviewProps) => {
  const [isEditing, setIsEditing] = createSignal(false)
  const [content, setContent] = createSignal(props.content)
  let editorRef: HTMLDivElement | undefined
  let highlightRef: HTMLPreElement | undefined
  let lineNumbersRef: HTMLDivElement | undefined

  const language = () => props.language || detectLanguage(content())

  /**
   * Обновляет подсветку синтаксиса
   */
  const updateHighlight = () => {
    if (!highlightRef) return

    const code = content() || ''
    const lang = language()

    try {
      if (Prism.languages[lang]) {
        highlightRef.innerHTML = Prism.highlight(code, Prism.languages[lang], lang)
      } else {
        highlightRef.textContent = code
      }
    } catch (e) {
      console.error('Error highlighting code:', e)
      highlightRef.textContent = code
    }
  }

  /**
   * Обновляет номера строк
   */
  const updateLineNumbers = () => {
    if (!lineNumbersRef) return

    const lineNumbers = generateLineNumbers(content())
    lineNumbersRef.innerHTML = lineNumbers
      .map((num) => `<div class="${styles.lineNumber}">${num}</div>`)
      .join('')
  }

  /**
   * Синхронизирует скролл между редактором и подсветкой
   */
  const syncScroll = () => {
    if (editorRef && highlightRef) {
      highlightRef.scrollTop = editorRef.scrollTop
      highlightRef.scrollLeft = editorRef.scrollLeft
    }
    if (editorRef && lineNumbersRef) {
      lineNumbersRef.scrollTop = editorRef.scrollTop
    }
  }

  /**
   * Обработчик изменения контента
   */
  const handleInput = (e: Event) => {
    const target = e.target as HTMLDivElement

    // Сохраняем текущую позицию курсора
    const selection = window.getSelection()
    let caretOffset = 0

    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0)
      const preCaretRange = range.cloneRange()
      preCaretRange.selectNodeContents(target)
      preCaretRange.setEnd(range.endContainer, range.endOffset)
      caretOffset = preCaretRange.toString().length
    }

    const newContent = target.textContent || ''
    setContent(newContent)
    props.onContentChange(newContent)
    updateHighlight()
    updateLineNumbers()

    // Восстанавливаем позицию курсора после обновления
    requestAnimationFrame(() => {
      if (target && selection) {
        try {
          const textNode = target.firstChild
          if (textNode && textNode.nodeType === Node.TEXT_NODE) {
            const range = document.createRange()
            const safeOffset = Math.min(caretOffset, textNode.textContent?.length || 0)
            range.setStart(textNode, safeOffset)
            range.setEnd(textNode, safeOffset)
            selection.removeAllRanges()
            selection.addRange(range)
          }
        } catch (error) {
          console.warn('Could not restore caret position:', error)
        }
      }
    })
  }

  /**
   * Обработчик сохранения
   */
  const handleSave = () => {
    if (props.onSave) {
      props.onSave(content())
    }
    setIsEditing(false)
  }

  /**
   * Обработчик отмены
   */
  const handleCancel = () => {
    const originalContent = props.content
    setContent(originalContent) // Возвращаем исходный контент

    // Обновляем содержимое редактируемой области
    if (editorRef) {
      editorRef.textContent = originalContent
    }

    if (props.onCancel) {
      props.onCancel()
    }
    setIsEditing(false)
  }

  /**
   * Обработчик клавиш
   */
  const handleKeyDown = (e: KeyboardEvent) => {
    // Ctrl+Enter или Cmd+Enter для сохранения
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSave()
      return
    }

    // Escape для отмены
    if (e.key === 'Escape') {
      e.preventDefault()
      handleCancel()
      return
    }

    // Tab для отступа
    if (e.key === 'Tab') {
      e.preventDefault()
      const selection = window.getSelection()
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0)
        range.deleteContents()
        range.insertNode(document.createTextNode('  ')) // Два пробела
        range.collapse(false)
        selection.removeAllRanges()
        selection.addRange(range)
        handleInput(e)
      }
    }
  }

  // Эффект для обновления контента при изменении props
  createEffect(() => {
    if (!isEditing()) {
      const formattedContent =
        language() === 'markup' || language() === 'html' ? formatHtmlContent(props.content) : props.content
      setContent(formattedContent)
      updateHighlight()
      updateLineNumbers()
    }
  })

  // Эффект для обновления подсветки при изменении контента
  createEffect(() => {
    content() // Реактивность
    updateHighlight()
    updateLineNumbers()
  })

  // Эффект для синхронизации редактируемой области с content
  createEffect(() => {
    if (editorRef) {
      const currentContent = content()
      if (editorRef.textContent !== currentContent) {
        // Сохраняем позицию курсора
        const selection = window.getSelection()
        let caretOffset = 0

        if (selection && selection.rangeCount > 0 && isEditing()) {
          const range = selection.getRangeAt(0)
          const preCaretRange = range.cloneRange()
          preCaretRange.selectNodeContents(editorRef)
          preCaretRange.setEnd(range.endContainer, range.endOffset)
          caretOffset = preCaretRange.toString().length
        }

        editorRef.textContent = currentContent

        // Восстанавливаем курсор только в режиме редактирования
        if (isEditing() && selection) {
          requestAnimationFrame(() => {
            try {
              const textNode = editorRef?.firstChild
              if (textNode && textNode.nodeType === Node.TEXT_NODE) {
                const range = document.createRange()
                const safeOffset = Math.min(caretOffset, textNode.textContent?.length || 0)
                range.setStart(textNode, safeOffset)
                range.setEnd(textNode, safeOffset)
                selection.removeAllRanges()
                selection.addRange(range)
              }
            } catch (error) {
              console.warn('Could not restore caret position:', error)
            }
          })
        }
      }
    }
  })

  onMount(() => {
    const formattedContent =
      language() === 'markup' || language() === 'html' ? formatHtmlContent(props.content) : props.content
    setContent(formattedContent)
    updateHighlight()
    updateLineNumbers()
  })

  return (
    <div class={styles.editableCodeContainer}>
      {/* Контейнер редактора - увеличиваем размер */}
      <div
        class={`${styles.editorWrapper} ${isEditing() ? styles.editorWrapperEditing : ''}`}
        style="height: 100%;"
      >
        {/* Номера строк */}
        <div ref={lineNumbersRef} class={styles.lineNumbersContainer} />

        {/* Подсветка синтаксиса (фон) - только в режиме редактирования */}
        <Show when={isEditing()}>
          <pre
            ref={highlightRef}
            class={`${styles.syntaxHighlight} language-${language()}`}
            aria-hidden="true"
          />
        </Show>

        {/* Редактируемая область */}
        <div
          ref={(el) => {
            editorRef = el
            // Синхронизируем содержимое при создании элемента
            if (el && el.textContent !== content()) {
              el.textContent = content()
            }
          }}
          contentEditable={isEditing()}
          class={`${styles.editorArea} ${isEditing() ? styles.editorAreaEditing : styles.editorAreaViewing}`}
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          onScroll={syncScroll}
          spellcheck={false}
        />

        {/* Превью для неактивного режима */}
        <Show when={!isEditing()}>
          <pre
            class={`${styles.codePreviewContainer} language-${language()}`}
            onClick={() => setIsEditing(true)}
            onScroll={(e) => {
              // Синхронизируем номера строк при скролле в режиме просмотра
              if (lineNumbersRef) {
                lineNumbersRef.scrollTop = (e.target as HTMLElement).scrollTop
              }
            }}
          >
            <code
              class={`language-${language()}`}
              innerHTML={(() => {
                try {
                  return Prism.highlight(content(), Prism.languages[language()], language())
                } catch {
                  return content()
                }
              })()}
            />
          </pre>
        </Show>
      </div>

      {/* Индикатор языка */}
      <span class={styles.languageBadge}>{language()}</span>

      {/* Плейсхолдер */}
      <Show when={!content()}>
        <div class={styles.placeholder} onClick={() => setIsEditing(true)}>
          {props.placeholder || 'Нажмите для редактирования...'}
        </div>
      </Show>

      {/* Кнопки управления внизу */}
      <Show when={props.showButtons}>
        <div class={styles.editorControls}>
          <Show
            when={isEditing()}
            fallback={
              <button class={styles.editButton} onClick={() => setIsEditing(true)}>
                ✏️ Редактировать
              </button>
            }
          >
            <div class={styles.editingControls}>
              <button class={styles.saveButton} onClick={handleSave}>
                💾 Сохранить (Ctrl+Enter)
              </button>
              <button class={styles.cancelButton} onClick={handleCancel}>
                ❌ Отмена (Esc)
              </button>
            </div>
          </Show>
        </div>
      </Show>
    </div>
  )
}

export default EditableCodePreview
