/**
 * Форматирование даты в формате "X дней назад"
 * @param timestamp - Временная метка
 * @returns Форматированная строка с относительной датой
 */
export function formatDateRelative(timestamp?: number): string {
  if (!timestamp) return 'Н/Д'

  const now = Math.floor(Date.now() / 1000)
  const diff = now - timestamp

  // Меньше минуты
  if (diff < 60) {
    return 'только что'
  }

  // Меньше часа
  if (diff < 3600) {
    const minutes = Math.floor(diff / 60)
    return `${minutes} ${getMinutesForm(minutes)} назад`
  }

  // Меньше суток
  if (diff < 86400) {
    const hours = Math.floor(diff / 3600)
    return `${hours} ${getHoursForm(hours)} назад`
  }

  // Меньше 30 дней
  if (diff < 2592000) {
    const days = Math.floor(diff / 86400)
    return `${days} ${getDaysForm(days)} назад`
  }

  // Меньше года
  if (diff < 31536000) {
    const months = Math.floor(diff / 2592000)
    return `${months} ${getMonthsForm(months)} назад`
  }

  // Больше года
  const years = Math.floor(diff / 31536000)
  return `${years} ${getYearsForm(years)} назад`
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
