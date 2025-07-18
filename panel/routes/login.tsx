/**
 * Компонент страницы входа
 * @module LoginPage
 */

import { useNavigate } from '@solidjs/router'
import { createSignal, onMount } from 'solid-js'
import publyLogo from '../assets/publy.svg?url'
import { useAuth } from '../context/auth'
import formStyles from '../styles/Form.module.css'
import styles from '../styles/Login.module.css'
import Button from '../ui/Button'
import LanguageSwitcher from '../ui/LanguageSwitcher'

/**
 * Компонент страницы входа
 */
const LoginPage = () => {
  console.log('[LoginPage] Initializing...')
  const [username, setUsername] = createSignal('')
  const [password, setPassword] = createSignal('')
  const [error, setError] = createSignal<string | null>(null)
  const [loading, setLoading] = createSignal(false)
  const auth = useAuth()
  const navigate = useNavigate()

  onMount(() => {
    console.log('[LoginPage] Component mounted')
    // Если пользователь уже авторизован, редиректим на админ-панель
    if (auth.isAuthenticated()) {
      console.log('[LoginPage] User already authenticated, redirecting to admin...')
      navigate('/admin')
    }
  })

  const handleSubmit = async (e: Event) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await auth.login(username(), password())
      navigate('/admin')
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Ошибка при входе')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div class={styles['login-container']}>
      <div class={styles['login-header']}>
        <LanguageSwitcher />
      </div>
      <div class={styles['login-form-container']}>
        <form class={formStyles.form} onSubmit={handleSubmit}>
          <img src={publyLogo} alt="Logo" class={styles['login-logo']} />
          <div class={formStyles.fieldGroup}>
            <input
              type="email"
              value={username()}
              onInput={(e) => setUsername(e.currentTarget.value)}
              placeholder="admin@media"
              required
              class={`${formStyles.input} ${error() ? formStyles.error : ''}`}
              disabled={loading()}
            />
          </div>

          <div class={formStyles.fieldGroup}>
            <input
              type="password"
              value={password()}
              onInput={(e) => setPassword(e.currentTarget.value)}
              placeholder="••••••••"
              required
              class={`${formStyles.input} ${error() ? formStyles.error : ''}`}
              disabled={loading()}
            />
          </div>

          {error() && (
            <div class={formStyles.fieldError}>
              <span class={formStyles.errorIcon}>⚠️</span>
              {error()}
            </div>
          )}

          <div class={formStyles.actions} style={{ margin: 'auto' }}>
            <Button
              variant="primary"
              type="submit"
              loading={loading()}
              disabled={loading() || !username() || !password()}
              onClick={handleSubmit}
            >
              Войти
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default LoginPage
