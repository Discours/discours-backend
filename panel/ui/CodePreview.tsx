import { createMemo, JSX, Show } from 'solid-js'
import 'prismjs/themes/prism-tomorrow.css'

import styles from '../styles/CodePreview.module.css'
import { detectLanguage, formatCode, highlightCode } from '../utils/codeHelpers'

interface CodePreviewProps extends JSX.HTMLAttributes<HTMLDivElement> {
  content: string
  language?: string
  maxHeight?: string
  showLineNumbers?: boolean
  autoFormat?: boolean
  editable?: boolean
  onEdit?: () => void
}

/**
 * Компонент для отображения кода с подсветкой синтаксиса
 *
 * @example
 * ```tsx
 * <CodePreview
 *   content='{"key": "value"}'
 *   language="json"
 *   showLineNumbers={true}
 *   editable={true}
 *   onEdit={() => setIsEditing(true)}
 * />
 * ```
 */
const CodePreview = (props: CodePreviewProps) => {
  // Реактивные вычисления
  const language = createMemo(() => props.language || detectLanguage(props.content))
  const formattedContent = createMemo(() =>
    props.autoFormat ? formatCode(props.content, language()) : props.content
  )
  const highlightedCode = createMemo(() => highlightCode(formattedContent(), language()))
  const isEmpty = createMemo(() => !props.content?.trim())

  return (
    <div
      class={`${styles.codePreview} ${props.editable ? styles.codePreviewContainer : ''} ${props.class || ''}`}
      style={`max-height: ${props.maxHeight || '500px'}; ${props.style || ''}`}
      onClick={props.editable ? props.onEdit : undefined}
      role={props.editable ? 'button' : 'presentation'}
      tabindex={props.editable ? 0 : undefined}
      onKeyDown={(e) => {
        if (props.editable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          props.onEdit?.()
        }
      }}
    >
      <div class={styles.codeContainer}>
        {/* Область кода */}
        <div class={styles.codeArea}>
          <Show
            when={!isEmpty()}
            fallback={
              <div class={`${styles.placeholder} ${props.editable ? styles.placeholderClickable : ''}`}>
                {props.editable ? 'Нажмите для редактирования...' : 'Нет содержимого'}
              </div>
            }
          >
            <pre class={styles.codePreviewContent}>
              <code class={`language-${language()}`} innerHTML={highlightedCode()} />
            </pre>
          </Show>
        </div>
      </div>

      {/* Индикаторы */}
      <div class={styles.controlsLeft}>
        <span class={styles.languageBadge}>{language()}</span>

        <Show when={props.editable}>
          <div class={styles.statusIndicator}>
            <div class={`${styles.statusDot} ${styles.idle}`} />
            <span>Только чтение</span>
          </div>
        </Show>
      </div>

      {/* Кнопка редактирования */}
      <Show when={props.editable && !isEmpty()}>
        <div class={styles.controlsRight}>
          <button
            class={styles.editButton}
            onClick={(e) => {
              e.stopPropagation()
              props.onEdit?.()
            }}
            title="Редактировать код"
          >
            ✏️ Редактировать
          </button>
        </div>
      </Show>
    </div>
  )
}

export default CodePreview
export { detectLanguage, formatCode }
