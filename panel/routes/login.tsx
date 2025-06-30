/**
 * Компонент страницы входа
 * @module LoginPage
 */

import { useNavigate } from '@solidjs/router'
import { createSignal, onMount } from 'solid-js'
import publyLogo from '../assets/publy.svg?url'
import { useAuth } from '../context/auth'
import styles from '../styles/Login.module.css'
import Button from '../ui/Button'

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
      <form class={styles['login-form']} onSubmit={handleSubmit}>
        <img src={publyLogo} alt="Logo" class={styles['login-logo']} />
        <h1>Вход в панель администратора</h1>

        {error() && <div class={styles['error-message']}>{error()}</div>}

        <div class={styles['form-group']}>
          <label for="username">Имя пользователя</label>
          <input
            id="username"
            type="text"
            value={username()}
            onInput={(e) => setUsername(e.currentTarget.value)}
            disabled={loading()}
            required
          />
        </div>

        <div class={styles['form-group']}>
          <label for="password">Пароль</label>
          <input
            id="password"
            type="password"
            value={password()}
            onInput={(e) => setPassword(e.currentTarget.value)}
            disabled={loading()}
            required
          />
        </div>

        <Button type="submit" variant="primary" disabled={loading()} loading={loading()}>
          {loading() ? 'Вход...' : 'Войти'}
        </Button>
      </form>
    </div>
  )
}

export default LoginPage
