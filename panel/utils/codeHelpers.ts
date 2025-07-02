// Prism.js временно отключен для упрощения загрузки

/**
 * Определяет язык контента (html, json, javascript, css или plaintext)
 */
export function detectLanguage(content: string): string {
  if (!content?.trim()) return ''

  try {
    JSON.parse(content)
    return 'json'
  } catch {
    // HTML/XML detection
    if (/<[^>]*>/g.test(content)) {
      return 'html'
    }

    // CSS detection
    if (/\{[^}]*\}/.test(content) && /[#.]\w+|@\w+/.test(content)) {
      return 'css'
    }

    // JavaScript detection
    if (/\b(function|const|let|var|class|import|export)\b/.test(content)) {
      return 'javascript'
    }
  }

  return ''
}

/**
 * Форматирует XML/HTML с отступами используя DOMParser
 */
export function formatXML(xml: string): string {
  if (!xml?.trim()) return ''

  try {
    // Пытаемся распарсить как HTML
    const parser = new DOMParser()
    let doc: Document

    // Оборачиваем в корневой элемент, если это фрагмент
    const wrappedXml =
      xml.trim().startsWith('<html') || xml.trim().startsWith('<!DOCTYPE') ? xml : `<div>${xml}</div>`

    doc = parser.parseFromString(wrappedXml, 'text/html')

    // Проверяем на ошибки парсинга
    const parserError = doc.querySelector('parsererror')
    if (parserError) {
      // Если HTML парсинг не удался, пытаемся как XML
      doc = parser.parseFromString(wrappedXml, 'application/xml')
      const xmlError = doc.querySelector('parsererror')
      if (xmlError) {
        // Если и XML не удался, возвращаем исходный код
        return xml
      }
    }

    // Извлекаем содержимое body или корневого элемента
    const body = doc.body || doc.documentElement
    const rootElement = xml.trim().startsWith('<div>') ? body.firstChild : body

    if (!rootElement) return xml

    // Форматируем рекурсивно
    return formatNode(rootElement as Element, 0)
  } catch (error) {
    // В случае ошибки возвращаем исходный код
    console.warn('XML formatting failed:', error)
    return xml
  }
}

/**
 * Рекурсивно форматирует узел DOM
 */
function formatNode(node: Node, indentLevel: number): string {
  const indentSize = 2
  const indent = ' '.repeat(indentLevel * indentSize)
  const childIndent = ' '.repeat((indentLevel + 1) * indentSize)

  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent?.trim()
    return text ? text : ''
  }

  if (node.nodeType === Node.ELEMENT_NODE) {
    const element = node as Element
    const tagName = element.tagName.toLowerCase()
    const attributes = Array.from(element.attributes)
      .map((attr) => `${attr.name}="${attr.value}"`)
      .join(' ')

    const openTag = attributes ? `<${tagName} ${attributes}>` : `<${tagName}>`

    const closeTag = `</${tagName}>`

    // Самозакрывающиеся теги
    if (isSelfClosingTag(`<${tagName}>`)) {
      return `${indent}${openTag.replace('>', ' />')}`
    }

    // Если нет дочерних элементов
    if (element.childNodes.length === 0) {
      return `${indent}${openTag}${closeTag}`
    }

    // Если только один текстовый узел
    if (element.childNodes.length === 1 && element.firstChild?.nodeType === Node.TEXT_NODE) {
      const text = element.firstChild.textContent?.trim()
      if (text && text.length < 80) {
        // Короткий текст на одной строке
        return `${indent}${openTag}${text}${closeTag}`
      }
    }

    // Многострочный элемент
    let result = `${indent}${openTag}\n`

    for (const child of Array.from(element.childNodes)) {
      const childFormatted = formatNode(child, indentLevel + 1)
      if (childFormatted) {
        if (child.nodeType === Node.TEXT_NODE) {
          result += `${childIndent}${childFormatted}\n`
        } else {
          result += `${childFormatted}\n`
        }
      }
    }

    result += `${indent}${closeTag}`
    return result
  }

  return ''
}

/**
 * Проверяет, является ли тег самозакрывающимся
 */
function isSelfClosingTag(line: string): boolean {
  const selfClosingTags = [
    'br',
    'hr',
    'img',
    'input',
    'meta',
    'link',
    'area',
    'base',
    'col',
    'embed',
    'source',
    'track',
    'wbr'
  ]
  const tagMatch = line.match(/<(\w+)/)
  if (tagMatch) {
    const tagName = tagMatch[1].toLowerCase()
    return selfClosingTags.includes(tagName)
  }
  return false
}

/**
 * Форматирует JSON с отступами
 */
export function formatJSON(json: string): string {
  try {
    return JSON.stringify(JSON.parse(json), null, 2)
  } catch {
    return json
  }
}

/**
 * Форматирует код в зависимости от языка
 */
export function formatCode(content: string, language?: string): string {
  if (!content?.trim()) return ''

  const lang = language || detectLanguage(content)

  switch (lang) {
    case 'json':
      return formatJSON(content)
    case 'markup':
    case 'html':
      return formatXML(content)
    default:
      return content
  }
}

/**
 * Подсвечивает синтаксис кода с использованием простых правил CSS
 */
export function highlightCode(content: string, language?: string): string {
  if (!content?.trim()) return ''

  const lang = language || detectLanguage(content)

  if (lang === 'html' || lang === 'markup') {
    return highlightHTML(content)
  }

  if (lang === 'json') {
    return highlightJSON(content)
  }

  // Для других языков возвращаем исходный код
  return escapeHtml(content)
}

/**
 * Простая подсветка HTML с использованием CSS классов
 */
function highlightHTML(html: string): string {
  let highlighted = escapeHtml(html)

  // Подсвечиваем теги
  highlighted = highlighted.replace(
    /(&lt;\/?)([a-zA-Z][a-zA-Z0-9]*)(.*?)(&gt;)/g,
    '$1<span class="html-tag">$2</span><span class="html-attr">$3</span>$4'
  )

  // Подсвечиваем атрибуты
  highlighted = highlighted.replace(
    /(\s)([a-zA-Z-]+)(=)(&quot;.*?&quot;)/g,
    '$1<span class="html-attr-name">$2</span>$3<span class="html-attr-value">$4</span>'
  )

  // Подсвечиваем сами теги
  highlighted = highlighted.replace(
    /(&lt;\/?)([^&]*?)(&gt;)/g,
    '<span class="html-bracket">$1</span>$2<span class="html-bracket">$3</span>'
  )

  return highlighted
}

/**
 * Простая подсветка JSON
 */
function highlightJSON(json: string): string {
  let highlighted = escapeHtml(json)

  // Подсвечиваем строки
  highlighted = highlighted.replace(/(&quot;.*?&quot;)(?=\s*:)/g, '<span class="json-key">$1</span>')
  highlighted = highlighted.replace(/:\s*(&quot;.*?&quot;)/g, ': <span class="json-string">$1</span>')

  // Подсвечиваем числа
  highlighted = highlighted.replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="json-number">$1</span>')

  // Подсвечиваем boolean и null
  highlighted = highlighted.replace(/:\s*(true|false|null)/g, ': <span class="json-boolean">$1</span>')

  return highlighted
}

/**
 * Экранирует HTML символы
 */
function escapeHtml(unsafe: string): string {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/**
 * Обработчик Tab в редакторе - вставляет отступ вместо смены фокуса
 */
export function handleTabKey(event: KeyboardEvent): boolean {
  if (event.key !== 'Tab') return false

  event.preventDefault()

  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0) return true

  const range = selection.getRangeAt(0)
  const indent = event.shiftKey ? '' : '  ' // Shift+Tab для unindent (пока просто не добавляем)

  if (!event.shiftKey) {
    range.deleteContents()
    range.insertNode(document.createTextNode(indent))
    range.collapse(false)
    selection.removeAllRanges()
    selection.addRange(range)
  }

  return true
}

/**
 * Сохраняет и восстанавливает позицию курсора в contentEditable элементе
 */
export class CaretManager {
  private element: HTMLElement
  private offset = 0

  constructor(element: HTMLElement) {
    this.element = element
  }

  savePosition(): void {
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return

    const range = selection.getRangeAt(0)
    const preCaretRange = range.cloneRange()
    preCaretRange.selectNodeContents(this.element)
    preCaretRange.setEnd(range.endContainer, range.endOffset)
    this.offset = preCaretRange.toString().length
  }

  restorePosition(): void {
    const selection = window.getSelection()
    if (!selection) return

    try {
      const textNode = this.element.firstChild
      if (textNode && textNode.nodeType === Node.TEXT_NODE) {
        const range = document.createRange()
        const safeOffset = Math.min(this.offset, textNode.textContent?.length || 0)
        range.setStart(textNode, safeOffset)
        range.setEnd(textNode, safeOffset)
        selection.removeAllRanges()
        selection.addRange(range)
      }
    } catch (error) {
      console.warn('Could not restore caret position:', error)
    }
  }
}

/**
 * Настройки по умолчанию для редактора кода
 */
export const DEFAULT_EDITOR_CONFIG = {
  fontSize: 13,
  lineHeight: 1.5,
  tabSize: 2,
  fontFamily:
    '"JetBrains Mono", "Fira Code", "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Consolas", monospace',
  theme: 'dark',
  showLineNumbers: true,
  autoFormat: true,
  keyBindings: {
    save: ['Ctrl+Enter', 'Cmd+Enter'],
    cancel: ['Escape'],
    tab: ['Tab'],
    format: ['Ctrl+Shift+F', 'Cmd+Shift+F']
  }
} as const
