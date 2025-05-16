/**
 * Компонент страницы входа
 * @module LoginPage
 */

import { Component, createSignal } from 'solid-js'
import { login } from './auth'

interface LoginPageProps {
  onLoginSuccess?: () => void
}

/**
 * Компонент страницы входа
 */
const LoginPage: Component<LoginPageProps> = (props) => {
  const [email, setEmail] = createSignal('')
  const [password, setPassword] = createSignal('')
  const [isLoading, setIsLoading] = createSignal(false)
  const [error, setError] = createSignal<string | null>(null)

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
        // Вызываем коллбэк для оповещения родителя об успешном входе
        if (props.onLoginSuccess) {
          props.onLoginSuccess()
        }
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
