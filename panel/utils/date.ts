import { createMemo } from 'solid-js'
import { useI18n } from '../intl/i18n'

export type Language = 'ru' | 'en'

/**
 * Форматирование даты в формате "X дней назад" с поддержкой многоязычности
 * @param timestamp - Временная метка
 * @param language - Язык для форматирования ('ru' | 'en')
 * @returns Форматированная строка с относительной датой
 */
export function formatDateRelativeStatic(timestamp?: number, language: Language = 'ru'): string {
  if (!timestamp) return ''

  const now = Math.floor(Date.now() / 1000)
  const diff = now - timestamp

  // Меньше минуты
  if (diff < 60) {
    return language === 'ru' ? 'только что' : 'just now'
  }

  // Меньше часа
  if (diff < 3600) {
    const minutes = Math.floor(diff / 60)
    if (language === 'ru') {
      return `${minutes} ${getMinutesForm(minutes)} назад`
    } else {
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
    }
  }

  // Меньше суток
  if (diff < 86400) {
    const hours = Math.floor(diff / 3600)
    if (language === 'ru') {
      return `${hours} ${getHoursForm(hours)} назад`
    } else {
      return `${hours} hour${hours !== 1 ? 's' : ''} ago`
    }
  }

  // Меньше 30 дней
  if (diff < 2592000) {
    const days = Math.floor(diff / 86400)
    if (language === 'ru') {
      return `${days} ${getDaysForm(days)} назад`
    } else {
      return `${days} day${days !== 1 ? 's' : ''} ago`
    }
  }

  // Меньше года
  if (diff < 31536000) {
    const months = Math.floor(diff / 2592000)
    if (language === 'ru') {
      return `${months} ${getMonthsForm(months)} назад`
    } else {
      return `${months} month${months !== 1 ? 's' : ''} ago`
    }
  }

  // Больше года
  const years = Math.floor(diff / 31536000)
  if (language === 'ru') {
    return `${years} ${getYearsForm(years)} назад`
  } else {
    return `${years} year${years !== 1 ? 's' : ''} ago`
  }
}

/**
 * Реактивная версия форматирования даты, которая автоматически обновляется при смене языка
 * @param timestamp - Временная метка
 * @returns Реактивный сигнал с форматированной строкой
 */
export function formatDateRelative(timestamp?: number) {
  const { language } = useI18n()
  return createMemo(() => formatDateRelativeStatic(timestamp, language()))
}

/**
 * Получение правильной формы слова "минута" в зависимости от числа
 */
function getMinutesForm(minutes: number): string {
  if (minutes % 10 === 1 && minutes % 100 !== 11) {
    return 'минуту'
  } else if ([2, 3, 4].includes(minutes % 10) && ![12, 13, 14].includes(minutes % 100)) {
    return 'минуты'
  }
  return 'минут'
}

/**
 * Получение правильной формы слова "час" в зависимости от числа
 */
function getHoursForm(hours: number): string {
  if (hours % 10 === 1 && hours % 100 !== 11) {
    return 'час'
  } else if ([2, 3, 4].includes(hours % 10) && ![12, 13, 14].includes(hours % 100)) {
    return 'часа'
  }
  return 'часов'
}

/**
 * Получение правильной формы слова "день" в зависимости от числа
 */
function getDaysForm(days: number): string {
  if (days % 10 === 1 && days % 100 !== 11) {
    return 'день'
  } else if ([2, 3, 4].includes(days % 10) && ![12, 13, 14].includes(days % 100)) {
    return 'дня'
  }
  return 'дней'
}

/**
 * Получение правильной формы слова "месяц" в зависимости от числа
 */
function getMonthsForm(months: number): string {
  if (months % 10 === 1 && months % 100 !== 11) {
    return 'месяц'
  } else if ([2, 3, 4].includes(months % 10) && ![12, 13, 14].includes(months % 100)) {
    return 'месяца'
  }
  return 'месяцев'
}

/**
 * Получение правильной формы слова "год" в зависимости от числа
 */
function getYearsForm(years: number): string {
  if (years % 10 === 1 && years % 100 !== 11) {
    return 'год'
  } else if ([2, 3, 4].includes(years % 10) && ![12, 13, 14].includes(years % 100)) {
    return 'года'
  }
  return 'лет'
}
