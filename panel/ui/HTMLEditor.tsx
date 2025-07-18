/**
 * HTML редактор с подсветкой синтаксиса через contenteditable
 * @module HTMLEditor
 */

import Prism from 'prismjs'
import { createEffect, createSignal, onMount, untrack } from 'solid-js'
import 'prismjs/components/prism-markup'
import 'prismjs/themes/prism.css'
import styles from '../styles/Form.module.css'

interface HTMLEditorProps {
  value: string
  onInput: (value: string) => void
  placeholder?: string
  rows?: number
  class?: string
  disabled?: boolean
}

/**
 * Компонент HTML редактора с contenteditable и подсветкой синтаксиса
 */
const HTMLEditor = (props: HTMLEditorProps) => {
  let editorElement: HTMLDivElement | undefined
  const [isUpdating, setIsUpdating] = createSignal(false)

  // Функция для принудительного обновления подсветки
  const forceHighlight = (element?: Element) => {
    if (!element) return

    // Многократная попытка подсветки для надежности
    const attemptHighlight = (attempts = 0) => {
      if (attempts > 3) return // Максимум 3 попытки

      if (typeof window !== 'undefined' && window.Prism && element) {
        try {
          Prism.highlightElement(element)
        } catch (error) {
          console.warn('Prism highlight failed, retrying...', error)
          setTimeout(() => attemptHighlight(attempts + 1), 50)
        }
      } else {
        setTimeout(() => attemptHighlight(attempts + 1), 50)
      }
    }

    attemptHighlight()
  }

  onMount(() => {
    if (editorElement) {
      // Устанавливаем начальное содержимое сразу
      updateContentWithoutCursor()

      // Принудительно перезапускаем подсветку через короткий таймаут
      setTimeout(() => {
        if (editorElement) {
          const codeElement = editorElement.querySelector('code')
          if (codeElement) {
            forceHighlight(codeElement)
          }
        }
      }, 50)

      // Устанавливаем фокус в конец если есть содержимое
      if (props.value) {
        setTimeout(() => {
          const range = document.createRange()
          const selection = window.getSelection()
          const codeElement = editorElement?.querySelector('code')
          if (codeElement?.firstChild) {
            range.setStart(codeElement.firstChild, codeElement.firstChild.textContent?.length || 0)
            range.setEnd(codeElement.firstChild, codeElement.firstChild.textContent?.length || 0)
            selection?.removeAllRanges()
            selection?.addRange(range)
          }
        }, 100)
      }
    }
  })

  // Обновляем содержимое при изменении props.value извне
  createEffect(() => {
    const newValue = props.value

    untrack(() => {
      if (editorElement && !isUpdating()) {
        const currentText = getPlainText()

        // Обновляем только если значение действительно изменилось извне
        // и элемент не в фокусе (чтобы не мешать вводу)
        if (newValue !== currentText && document.activeElement !== editorElement) {
          updateContentWithoutCursor()
        }
      }
    })
  })

  const updateContent = () => {
    if (!editorElement || isUpdating()) return

    const value = untrack(() => props.value) || ''

    // Сохраняем позицию курсора более надежно
    const selection = window.getSelection()
    let savedRange: Range | null = null
    let cursorOffset = 0

    if (selection && selection.rangeCount > 0 && document.activeElement === editorElement) {
      const range = selection.getRangeAt(0)
      savedRange = range.cloneRange()

      // Вычисляем общий offset относительно всего текстового содержимого
      const walker = document.createTreeWalker(editorElement, NodeFilter.SHOW_TEXT, null)

      let node: Node | null = null
      let totalOffset = 0

      while ((node = walker.nextNode())) {
        if (node === range.startContainer) {
          cursorOffset = totalOffset + range.startOffset
          break
        }
        totalOffset += node.textContent?.length || 0
      }
    }

    if (value.trim()) {
      // Экранируем HTML для безопасности
      const escapedValue = value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')

      editorElement.innerHTML = `<code class="language-html">${escapedValue}</code>`

      // Применяем подсветку с дополнительной проверкой
      const codeElement = editorElement.querySelector('code')
      if (codeElement) {
        forceHighlight(codeElement)

        // Восстанавливаем позицию курсора только если элемент в фокусе
        if (savedRange && document.activeElement === editorElement) {
          setTimeout(() => {
            const walker = document.createTreeWalker(codeElement, NodeFilter.SHOW_TEXT, null)
            let currentOffset = 0
            let node: Node | null = null

            while ((node = walker.nextNode())) {
              const nodeLength = node.textContent?.length || 0
              if (currentOffset + nodeLength >= cursorOffset) {
                try {
                  const range = document.createRange()
                  const newSelection = window.getSelection()
                  const targetOffset = Math.min(cursorOffset - currentOffset, nodeLength)

                  range.setStart(node, targetOffset)
                  range.setEnd(node, targetOffset)
                  newSelection?.removeAllRanges()
                  newSelection?.addRange(range)
                } catch (_e) {
                  // Используем savedRange как резервный вариант
                  if (savedRange) {
                    const newSelection = window.getSelection()
                    newSelection?.removeAllRanges()
                    newSelection?.addRange(savedRange)
                  }
                }
                break
              }
              currentOffset += nodeLength
            }
          }, 0)
        }
      }
    } else {
      // Для пустого содержимого просто очищаем
      editorElement.innerHTML = ''
    }
  }

  const updateContentWithoutCursor = () => {
    if (!editorElement) return

    const value = props.value || ''

    if (value.trim()) {
      // Экранируем HTML для безопасности
      const escapedValue = value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')

      editorElement.innerHTML = `<code class="language-html">${escapedValue}</code>`

      // Применяем подсветку с дополнительной проверкой
      const codeElement = editorElement.querySelector('code')
      if (codeElement) {
        forceHighlight(codeElement)
      }
    } else {
      // Для пустого содержимого просто очищаем
      editorElement.innerHTML = ''
    }
  }

  const getPlainText = (): string => {
    if (!editorElement) return ''

    // Получаем текстовое содержимое с правильной обработкой новых строк
    let text = ''

    const processNode = (node: Node): void => {
      if (node.nodeType === Node.TEXT_NODE) {
        text += node.textContent || ''
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const element = node as Element

        // Обрабатываем элементы, которые должны создавать новые строки
        if (element.tagName === 'DIV' || element.tagName === 'P') {
          // Добавляем новую строку перед содержимым div/p (кроме первого)
          if (text && !text.endsWith('\n')) {
            text += '\n'
          }

          // Обрабатываем дочерние элементы
          for (const child of Array.from(element.childNodes)) {
            processNode(child)
          }

          // Добавляем новую строку после содержимого div/p
          if (!text.endsWith('\n')) {
            text += '\n'
          }
        } else if (element.tagName === 'BR') {
          text += '\n'
        } else {
          // Для других элементов просто обрабатываем содержимое
          for (const child of Array.from(element.childNodes)) {
            processNode(child)
          }
        }
      }
    }

    try {
      processNode(editorElement)
    } catch (_e) {
      // В случае ошибки возвращаем базовый textContent
      return editorElement.textContent || ''
    }

    // Убираем лишние новые строки в конце
    return text.replace(/\n+$/, '')
  }

  const handleInput = () => {
    if (!editorElement || isUpdating()) return

    setIsUpdating(true)

    const text = untrack(() => getPlainText())

    // Обновляем значение через props, используя untrack для избежания циклических обновлений
    untrack(() => props.onInput(text))

    // Отложенное обновление подсветки без влияния на курсор
    setTimeout(() => {
      // Используем untrack для всех операций чтения состояния
      untrack(() => {
        if (document.activeElement === editorElement && !isUpdating()) {
          const currentText = getPlainText()
          if (currentText === text && editorElement) {
            updateContent()
          }
        }
        setIsUpdating(false)
      })
    }, 100) // Ещё меньше задержка
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    // Поддержка Tab для отступов
    if (e.key === 'Tab') {
      e.preventDefault()
      const selection = window.getSelection()
      const range = selection?.getRangeAt(0)

      if (range) {
        const textNode = document.createTextNode('  ')
        range.insertNode(textNode)
        range.setStartAfter(textNode)
        range.setEndAfter(textNode)
        selection?.removeAllRanges()
        selection?.addRange(range)
      }

      // Обновляем содержимое без задержки для Tab
      untrack(() => {
        const text = getPlainText()
        props.onInput(text)
      })
      return
    }

    // Для Enter не делаем ничего - полностью полагаемся на handleInput
    if (e.key === 'Enter') {
      // Полностью доверяем handleInput обработать изменение
      return
    }
  }

  const handlePaste = (e: ClipboardEvent) => {
    e.preventDefault()
    const text = e.clipboardData?.getData('text/plain') || ''
    document.execCommand('insertText', false, text)

    // Обновляем значение после вставки
    setTimeout(() => {
      untrack(() => {
        const newText = getPlainText()
        props.onInput(newText)
      })
    }, 10)
  }

  return (
    <div
      ref={editorElement}
      class={`${styles.htmlEditorContenteditable} ${props.class || ''}`}
      contenteditable={!props.disabled}
      data-placeholder={props.placeholder}
      onInput={handleInput}
      onKeyDown={handleKeyDown}
      onPaste={handlePaste}
      style={{
        'min-height': `${(props.rows || 6) * 1.6}em`
      }}
    />
  )
}

export default HTMLEditor
