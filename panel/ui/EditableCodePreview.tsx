import Prism from 'prismjs'
import { createEffect, createSignal, onMount } from 'solid-js'
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
 * Редактируемый компонент для кода с подсветкой синтаксиса
 */
const EditableCodePreview = (props: EditableCodePreviewProps) => {
  const [isEditing, setIsEditing] = createSignal(false)
  const [content, setContent] = createSignal(props.content)
  let editorRef: HTMLDivElement | undefined
  let highlightRef: HTMLPreElement | undefined

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
   * Синхронизирует скролл между редактором и подсветкой
   */
  const syncScroll = () => {
    if (editorRef && highlightRef) {
      highlightRef.scrollTop = editorRef.scrollTop
      highlightRef.scrollLeft = editorRef.scrollLeft
    }
  }

  /**
   * Обработчик изменения контента
   */
  const handleInput = (e: Event) => {
    const target = e.target as HTMLDivElement
    const newContent = target.textContent || ''
    setContent(newContent)
    props.onContentChange(newContent)
    updateHighlight()
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
    setContent(props.content) // Возвращаем исходный контент
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
      // const target = e.target as HTMLDivElement
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
      setContent(props.content)
      updateHighlight()
    }
  })

  // Эффект для обновления подсветки при изменении контента
  createEffect(() => {
    content() // Реактивность
    updateHighlight()
  })

  onMount(() => {
    updateHighlight()
  })

  return (
    <div class={styles.editableCodeContainer}>
      {/* Кнопки управления */}
      {props.showButtons !== false && (
        <div class={styles.editorControls}>
          {!isEditing() ? (
            <button class={styles.editButton} onClick={() => setIsEditing(true)}>
              ✏️ Редактировать
            </button>
          ) : (
            <div class={styles.editingControls}>
              <button class={styles.saveButton} onClick={handleSave}>
                💾 Сохранить (Ctrl+Enter)
              </button>
              <button class={styles.cancelButton} onClick={handleCancel}>
                ❌ Отмена (Esc)
              </button>
            </div>
          )}
        </div>
      )}

      {/* Контейнер редактора */}
      <div
        class={styles.editorWrapper}
        style={`max-height: ${props.maxHeight || '70vh'}; ${isEditing() ? 'border: 2px solid #007acc;' : ''}`}
      >
        {/* Подсветка синтаксиса (фон) */}
        <pre
          ref={highlightRef}
          class={`${styles.syntaxHighlight} language-${language()}`}
          style="position: absolute; top: 0; left: 0; pointer-events: none; color: transparent; background: transparent; margin: 0; padding: 12px; font-family: 'Fira Code', monospace; font-size: 14px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; overflow: hidden;"
          aria-hidden="true"
        />

        {/* Редактируемая область */}
        <div
          ref={editorRef}
          contentEditable={isEditing()}
          class={styles.editorArea}
          style={`
            position: relative;
            z-index: 1;
            background: ${isEditing() ? 'rgba(0, 0, 0, 0.05)' : 'transparent'};
            color: ${isEditing() ? 'rgba(255, 255, 255, 0.9)' : 'transparent'};
            margin: 0;
            padding: 12px;
            font-family: 'Fira Code', monospace;
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
            overflow-y: auto;
            outline: none;
            cursor: ${isEditing() ? 'text' : 'default'};
            caret-color: ${isEditing() ? '#fff' : 'transparent'};
          `}
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          onScroll={syncScroll}
          spellcheck={false}
        >
          {content()}
        </div>

        {/* Превью для неактивного режима */}
        {!isEditing() && (
          <pre
            class={`${styles.codePreview} language-${language()}`}
            style={`
              position: absolute;
              top: 0;
              left: 0;
              margin: 0;
              padding: 12px;
              font-family: 'Fira Code', monospace;
              font-size: 14px;
              line-height: 1.5;
              white-space: pre-wrap;
              word-wrap: break-word;
              background: transparent;
              cursor: pointer;
            `}
            onClick={() => setIsEditing(true)}
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
        )}
      </div>

      {/* Плейсхолдер */}
      {!content() && (
        <div
          class={styles.placeholder}
          onClick={() => setIsEditing(true)}
          style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #666; cursor: pointer; font-style: italic;"
        >
          {props.placeholder || 'Нажмите для редактирования...'}
        </div>
      )}

      {/* Индикатор языка */}
      <span class={styles.languageBadge}>{language()}</span>
    </div>
  )
}

export default EditableCodePreview
