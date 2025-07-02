import { Component, createSignal } from 'solid-js'
import { Language, useI18n } from '../intl/i18n'
import styles from '../styles/Button.module.css'

/**
 * Компонент переключателя языков
 */
const LanguageSwitcher: Component = () => {
  const { setLanguage, isRussian, language } = useI18n()
  const [isLoading, setIsLoading] = createSignal(false)

  /**
   * Переключает язык между русским и английским
   */
  const toggleLanguage = () => {
    const currentLang = language()
    const newLanguage: Language = isRussian() ? 'en' : 'ru'
    console.log('Переключение языка:', { from: currentLang, to: newLanguage })

    // Показываем индикатор загрузки
    setIsLoading(true)

    // Небольшая задержка для отображения индикатора
    setTimeout(() => {
      setLanguage(newLanguage)
      // Примечание: страница будет перезагружена, поэтому нет необходимости сбрасывать isLoading
    }, 100)
  }

  return (
    <button
      class={`${styles.button} ${styles.secondary} ${styles.small} ${styles['language-button']}`}
      onClick={toggleLanguage}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          toggleLanguage()
        }
      }}
      title={isRussian() ? 'Switch to English' : 'Переключить на русский'}
      aria-label={isRussian() ? 'Switch to English' : 'Переключить на русский'}
      disabled={isLoading()}
    >
      {isLoading() ? <span class={styles['language-loader']} /> : isRussian() ? 'EN' : 'RU'}
    </button>
  )
}

export default LanguageSwitcher
