import { JSX } from 'solid-js'
import styles from '../styles/CodePreview.module.css'

/**
 * Компонент для простого просмотра текста без подсветки syntax
 * Убирает HTML теги и показывает чистый текст
 */

interface TextPreviewProps extends JSX.HTMLAttributes<HTMLPreElement> {
  content: string
  maxHeight?: string
  showLineNumbers?: boolean
}

/**
 * Убирает HTML теги и декодирует HTML entity
 */
function stripHtmlTags(text: string): string {
  // Убираем HTML теги
  let cleaned = text.replace(/<[^>]*>/g, '')

  // Декодируем базовые HTML entity
  cleaned = cleaned
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&nbsp;/g, ' ')

  return cleaned.trim()
}

const TextPreview = (props: TextPreviewProps) => {
  const cleanedContent = () => stripHtmlTags(props.content)

  const contentWithLines = () => {
    if (!props.showLineNumbers) return cleanedContent()

    const lines = cleanedContent().split('\n')
    return lines.map((line, index) => `${(index + 1).toString().padStart(3, ' ')} | ${line}`).join('\n')
  }

  return (
    <pre
      {...props}
      class={`${styles.codePreview} ${props.class || ''}`}
      style={`
        max-height: ${props.maxHeight || '60vh'};
        overflow-y: auto;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;
        word-wrap: break-word;
        ${props.style || ''}
      `}
    >
      <code class={styles.code}>{contentWithLines()}</code>
    </pre>
  )
}

export default TextPreview
