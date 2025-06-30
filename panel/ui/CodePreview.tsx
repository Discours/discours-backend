import Prism from 'prismjs'
import { JSX } from 'solid-js'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-markup'
import 'prismjs/themes/prism-tomorrow.css'

import styles from '../styles/CodePreview.module.css'

/**
 * Определяет язык контента (html или json)
 */
function detectLanguage(content: string): string {
  try {
    JSON.parse(content)
    return 'json'
  } catch {
    if (/<[^>]*>/g.test(content)) {
      return 'markup'
    }
  }
  return 'plaintext'
}

/**
 * Форматирует XML/HTML с отступами
 */
function prettyFormatXML(xml: string): string {
  let formatted = ''
  const reg = /(>)(<)(\/*)/g
  const res = xml.replace(reg, '$1\r\n$2$3')
  let pad = 0
  res.split('\r\n').forEach((node) => {
    let indent = 0
    if (node.match(/.+<\/\w[^>]*>$/)) {
      indent = 0
    } else if (node.match(/^<\//)) {
      if (pad !== 0) pad -= 2
    } else if (node.match(/^<\w([^>]*[^/])?>.*$/)) {
      indent = 2
    } else {
      indent = 0
    }
    formatted += `${' '.repeat(pad)}${node}\r\n`
    pad += indent
  })
  return formatted.trim()
}

/**
 * Форматирует и подсвечивает код
 */
function formatCode(content: string): string {
  const language = detectLanguage(content)

  if (language === 'json') {
    try {
      const formatted = JSON.stringify(JSON.parse(content), null, 2)
      return Prism.highlight(formatted, Prism.languages[language], language)
    } catch {
      return content
    }
  } else if (language === 'markup') {
    const formatted = prettyFormatXML(content)
    return Prism.highlight(formatted, Prism.languages[language], language)
  }

  return content
}

interface CodePreviewProps extends JSX.HTMLAttributes<HTMLPreElement> {
  content: string
  language?: string
  maxHeight?: string
}

const CodePreview = (props: CodePreviewProps) => {
  const language = () => props.language || detectLanguage(props.content)
  // const formattedCode = () => formatCode(props.content)

  const numberedCode = () => {
    const lines = props.content.split('\n')
    return lines
      .map((line, index) => `<span class="${styles.lineNumber}">${index + 1}</span>${line}`)
      .join('\n')
  }

  return (
    <pre
      {...props}
      class={`${styles.codePreview} ${props.class || ''}`}
      style={`max-height: ${props.maxHeight || '500px'}; overflow-y: auto; ${props.style || ''}`}
    >
      <code
        class={`language-${language()} ${styles.code}`}
        innerHTML={Prism.highlight(numberedCode(), Prism.languages[language()], language())}
      />
      {props.language && <span class={styles.languageBadge}>{props.language}</span>}
    </pre>
  )
}

export default CodePreview
export { detectLanguage, formatCode }
