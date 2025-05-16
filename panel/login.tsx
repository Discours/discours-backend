/**
 * Компонент страницы входа
 * @module LoginPage
 */

import { useNavigate } from '@solidjs/router'
import { Component, createSignal, onMount } from 'solid-js'
import { login, isAuthenticated } from './auth'

/**
 * Компонент страницы входа
 */
const LoginPage: Component = () => {
  const [email, setEmail] = createSignal('')
  const [password, setPassword] = createSignal('')
  const [isLoading, setIsLoading] = createSignal(false)
  const [error, setError] = createSignal<string | null>(null)
  const navigate = useNavigate()

  /**
   * Проверка авторизации при загрузке компонента
   * и перенаправление если пользователь уже авторизован
   */
  onMount(() => {
    // Если пользователь уже авторизован, перенаправляем на админ-панель
    if (isAuthenticated()) {
      window.location.href = '/admin'
    }
  })

  /**
   * Обработчик отправки формы входа
   * @param e - Событие отправки формы
   */
  const handleSubmit = async (e: Event) => {
    e.preventDefault()

    // Очищаем пробелы в email
    const cleanEmail = email().trim()

    if (!cleanEmail || !password()) {
      setError('Пожалуйста, заполните все поля')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      // Используем функцию login из модуля auth
      const loginSuccessful = await login({
        email: cleanEmail,
        password: password()
      })

      if (loginSuccessful) {
        // Используем прямое перенаправление для надежности
        window.location.href = '/admin'
      } else {
        throw new Error('Вход не выполнен')
      }
    } catch (err) {
      console.error('Ошибка при входе:', err)
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка')
      setIsLoading(false)
    }
  }

  return (
    <div class="login-page">
      <div class="login-container">
        <h1>Вход в систему</h1>

        {error() && <div class="error-message">{error()}</div>}

        <form onSubmit={handleSubmit}>
          <div class="form-group">
            <label for="email">Email</label>
            <input
              type="email"
              id="email"
              value={email()}
              onInput={(e) => setEmail(e.currentTarget.value)}
              disabled={isLoading()}
              autocomplete="username"
              required
            />
          </div>

          <div class="form-group">
            <label for="password">Пароль</label>
            <input
              type="password"
              id="password"
              value={password()}
              onInput={(e) => setPassword(e.currentTarget.value)}
              disabled={isLoading()}
              autocomplete="current-password"
              required
            />
          </div>

          <button type="submit" disabled={isLoading()}>
            {isLoading() ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage
