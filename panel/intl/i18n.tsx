import {
  createContext,
  createEffect,
  createSignal,
  JSX,
  onCleanup,
  onMount,
  ParentComponent,
  useContext
} from 'solid-js'
import strings from './strings.json'

/**
 * Тип для поддерживаемых языков
 */
export type Language = 'ru' | 'en'

/**
 * Ключ для сохранения языка в localStorage
 */
const STORAGE_KEY = 'admin-language'

/**
 * Регекс для детекции кириллических символов
 */
const CYRILLIC_REGEX = /[\u0400-\u04FF]/

/**
 * Контекст интернационализации
 */
interface I18nContextType {
  language: () => Language
  setLanguage: (lang: Language) => void
  t: (key: string) => string
  tr: (text: string) => string
  isRussian: () => boolean
}

/**
 * Создаем контекст
 */
const I18nContext = createContext<I18nContextType>()

/**
 * Функция для перевода строки
 */
const translateString = (text: string, language: Language): string => {
  // Если язык русский или строка не содержит кириллицу, возвращаем как есть
  if (language === 'ru' || !CYRILLIC_REGEX.test(text)) {
    return text
  }

  // Ищем перевод в словаре
  const translation = strings[text as keyof typeof strings]
  return translation || text
}

/**
 * Автоматический переводчик элементов
 * Перехватывает создание JSX элементов и автоматически делает кириллические строки реактивными
 */
const AutoTranslator = (props: { children: JSX.Element; language: () => Language }) => {
  let containerRef: HTMLDivElement | undefined
  let observer: MutationObserver | undefined

  // Кэш для переведенных элементов
  const translationCache = new WeakMap<Node, string>()

  // Функция для обновления текстового содержимого
  const updateTextContent = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const originalText = node.textContent || ''

      // Проверяем, содержит ли кириллицу
      if (CYRILLIC_REGEX.test(originalText)) {
        const currentLang = props.language()
        const translatedText = translateString(originalText, currentLang)

        // Обновляем только если текст изменился
        if (node.textContent !== translatedText) {
          console.log(`📝 Переводим текстовый узел "${originalText}" -> "${translatedText}"`)
          node.textContent = translatedText
          translationCache.set(node, originalText) // Сохраняем оригинал
        }
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const element = node as Element

      // Переводим атрибуты
      const attributesToTranslate = ['title', 'placeholder', 'alt', 'aria-label', 'data-placeholder']
      attributesToTranslate.forEach((attr) => {
        const value = element.getAttribute(attr)
        if (value && CYRILLIC_REGEX.test(value)) {
          const currentLang = props.language()
          const translatedValue = translateString(value, currentLang)
          if (translatedValue !== value) {
            console.log(`📝 Переводим атрибут ${attr}="${value}" -> "${translatedValue}"`)
            element.setAttribute(attr, translatedValue)
          }
        }
      })

      // Специальная обработка элементов с текстом (кнопки, ссылки, лейблы, заголовки и т.д.)
      const textElements = [
        'BUTTON',
        'A',
        'LABEL',
        'SPAN',
        'DIV',
        'P',
        'H1',
        'H2',
        'H3',
        'H4',
        'H5',
        'H6',
        'TD',
        'TH'
      ]
      if (textElements.includes(element.tagName)) {
        // Ищем прямые текстовые узлы внутри элемента
        const directTextNodes = Array.from(element.childNodes).filter(
          (child) => child.nodeType === Node.TEXT_NODE && child.textContent?.trim()
        )

        // Если есть прямые текстовые узлы, обрабатываем их
        directTextNodes.forEach((textNode) => {
          const text = textNode.textContent || ''
          if (CYRILLIC_REGEX.test(text)) {
            const currentLang = props.language()
            const translatedText = translateString(text, currentLang)
            if (translatedText !== text) {
              console.log(`📝 Переводим "${text}" -> "${translatedText}" (${element.tagName})`)
              textNode.textContent = translatedText
              translationCache.set(textNode, text)
            }
          }
        })

        // Дополнительная проверка для кнопок с вложенными элементами
        if (element.tagName === 'BUTTON' && directTextNodes.length === 0) {
          // Если у кнопки нет прямых текстовых узлов, но есть вложенные элементы
          const buttonText = element.textContent?.trim()
          if (buttonText && CYRILLIC_REGEX.test(buttonText)) {
            const valueAttr = element.getAttribute('value')
            if (valueAttr && CYRILLIC_REGEX.test(valueAttr)) {
              const currentLang = props.language()
              const translatedValue = translateString(valueAttr, currentLang)
              if (translatedValue !== valueAttr) {
                console.log(`📝 Переводим value="${valueAttr}" -> "${translatedValue}"`)
                element.setAttribute('value', translatedValue)
              }
            }
          }
        }
      }

      // Рекурсивно обрабатываем дочерние узлы
      Array.from(node.childNodes).forEach(updateTextContent)
    }
  }

  // Функция для обновления всего контейнера
  const updateAll = () => {
    if (containerRef) {
      updateTextContent(containerRef)
    }
  }

  // Настройка MutationObserver для отслеживания новых элементов
  const setupObserver = () => {
    if (!containerRef) return

    observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(updateTextContent)
        }
      })
    })

    observer.observe(containerRef, {
      childList: true,
      subtree: true
    })
  }

  // Реагируем на изменения языка
  createEffect(() => {
    const currentLang = props.language()
    console.log('🌐 Язык изменился на:', currentLang)
    updateAll() // обновляем все тексты при изменении языка
  })

  // Инициализация при монтировании
  onMount(() => {
    if (containerRef) {
      updateAll()
      setupObserver()
    }
  })

  // Очистка
  onCleanup(() => {
    if (observer) {
      observer.disconnect()
    }
  })

  return (
    <div ref={containerRef} style={{ display: 'contents' }}>
      {props.children}
    </div>
  )
}

/**
 * Провайдер интернационализации с автоматическим переводом
 */
export const I18nProvider: ParentComponent = (props) => {
  const [language, setLanguage] = createSignal<Language>('ru')

  /**
   * Функция перевода по ключу
   */
  const t = (key: string): string => {
    const currentLang = language()
    if (currentLang === 'ru') {
      return key
    }

    const translation = strings[key as keyof typeof strings]
    return translation || key
  }

  /**
   * Реактивная функция перевода - использует текущий язык
   */
  const tr = (text: string): string => {
    const currentLang = language()
    if (currentLang === 'ru' || !CYRILLIC_REGEX.test(text)) {
      return text
    }
    const translation = strings[text as keyof typeof strings]
    return translation || text
  }

  /**
   * Проверка, русский ли язык
   */
  const isRussian = () => language() === 'ru'

  /**
   * Загружаем язык из localStorage при инициализации
   */
  onMount(() => {
    const savedLanguage = localStorage.getItem(STORAGE_KEY) as Language
    if (savedLanguage && (savedLanguage === 'ru' || savedLanguage === 'en')) {
      setLanguage(savedLanguage)
    }
  })

  /**
   * Сохраняем язык в localStorage при изменении и перезагружаем страницу
   */
  const handleLanguageChange = (lang: Language) => {
    // Сохраняем новый язык
    localStorage.setItem(STORAGE_KEY, lang)

    // Если язык действительно изменился
    if (language() !== lang) {
      console.log(`🔄 Перезагрузка страницы после смены языка с ${language()} на ${lang}`)

      // Устанавливаем сигнал (хотя это не обязательно при перезагрузке)
      setLanguage(lang)

      // Перезагружаем страницу для корректного обновления всех DOM элементов
      window.location.reload()
    } else {
      // Если язык не изменился, просто обновляем сигнал
      setLanguage(lang)
    }
  }

  const contextValue: I18nContextType = {
    language,
    setLanguage: handleLanguageChange,
    t,
    tr,
    isRussian
  }

  return (
    <I18nContext.Provider value={contextValue}>
      <AutoTranslator language={language}>{props.children}</AutoTranslator>
    </I18nContext.Provider>
  )
}

/**
 * Хук для использования контекста интернационализации
 */
export const useI18n = (): I18nContextType => {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return context
}

/**
 * Хук для получения функции перевода
 */
export const useTranslation = () => {
  const { t, tr, language, isRussian } = useI18n()
  return { t, tr, language: language(), isRussian: isRussian() }
}
