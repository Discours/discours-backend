/**
 * Компонент страницы входа
 * @module LoginPage
 */

import { Component, createSignal, Show } from 'solid-js'
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
  const [formSubmitting, setFormSubmitting] = createSignal(false)

  /**
   * Обработчик отправки формы входа
   * @param e - Событие отправки формы
   */
  const handleSubmit = async (e: Event) => {
    e.preventDefault()

    // Предотвращаем повторную отправку формы
    if (formSubmitting()) return

    // Очищаем пробелы в email
    const cleanEmail = email().trim()

    if (!cleanEmail || !password()) {
      setError('Пожалуйста, заполните все поля')
      return
    }

    setFormSubmitting(true)
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
    } finally {
      setFormSubmitting(false)
    }
  }

  return (
    <div class="login-page">
      <div class="login-container">
        <img src="https://testing.dscrs.site/logo.svg" alt="Logo" />
        <div class="error-message" style={{ opacity: error() ? 1 : 0 }}>{error()}</div>

        <form onSubmit={handleSubmit} method="post">
          <div class="form-group">
            <input
              type="email"
              id="email"
              name="email"
              placeholder="Email"
              value={email()}
              onInput={(e) => setEmail(e.currentTarget.value)}
              disabled={isLoading()}
              autocomplete="username"
              required
            />
          </div>

          <div class="form-group">
            <input
              type="password"
              id="password"
              name="password"
              placeholder="Пароль"
              value={password()}
              onInput={(e) => setPassword(e.currentTarget.value)}
              disabled={isLoading()}
              autocomplete="current-password"
              required
            />
          </div>

          <button type="submit" disabled={isLoading() || formSubmitting()}>
            {isLoading() ? (
              <>
                <span class="spinner"></span>
                Вход...
              </>
            ) : (
              'Войти'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage
