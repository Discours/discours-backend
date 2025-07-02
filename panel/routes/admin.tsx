/**
 * Компонент страницы администратора
 * @module AdminPage
 */

import { useNavigate, useParams } from '@solidjs/router'
import { Component, createEffect, createSignal, onMount, Show } from 'solid-js'
import publyLogo from '../assets/publy.svg?url'
import { logout } from '../context/auth'
import styles from '../styles/Admin.module.css'
import Button from '../ui/Button'
import CommunitySelector from '../ui/CommunitySelector'
import LanguageSwitcher from '../ui/LanguageSwitcher'
// Прямой импорт компонентов вместо ленивой загрузки
import AuthorsRoute from './authors'
import CollectionsRoute from './collections'
import CommunitiesRoute from './communities'
import EnvRoute from './env'
import InvitesRoute from './invites'
import ShoutsRoute from './shouts'
import { Topics as TopicsRoute } from './topics'

/**
 * Интерфейс свойств компонента AdminPage
 */
export interface AdminPageProps {
  apiUrl: string
  onLogout?: () => void
}

/**
 * Компонент страницы администратора
 */
const AdminPage: Component<AdminPageProps> = (props) => {
  console.log('[AdminPage] Initializing...')
  const navigate = useNavigate()
  const params = useParams()
  const [error, setError] = createSignal<string | null>(null)
  const [successMessage, setSuccessMessage] = createSignal<string | null>(null)
  const [currentTab, setCurrentTab] = createSignal<string>('authors')

  onMount(() => {
    console.log('[AdminPage] Component mounted')
    console.log('[AdminPage] Initial params:', params)
    // Если мы на корневом пути /admin, редиректим на /admin/authors
    if (!params.tab) {
      navigate('/admin/authors', { replace: true })
    } else {
      setCurrentTab(params.tab)
    }
  })

  // Отслеживаем изменения параметров роута
  createEffect(() => {
    console.log('[AdminPage] Params changed:', params)
    console.log('[AdminPage] Current tab param:', params.tab)
    const newTab = params.tab || 'authors'
    setCurrentTab(newTab)
    console.log('[AdminPage] Updated currentTab to:', newTab)
  })

  /**
   * Обрабатывает выход из системы
   */
  const handleLogout = async () => {
    try {
      await logout()
      if (props.onLogout) {
        props.onLogout()
      }
      navigate('/login')
    } catch (error) {
      setError(`Ошибка при выходе: ${(error as Error).message}`)
    }
  }

  /**
   * Обработчик ошибок
   */
  const handleError = (error: string) => {
    setError(error)
    // Скрываем ошибку через 5 секунд
    setTimeout(() => setError(null), 5000)
  }

  /**
   * Обработчик успешных операций
   */
  const handleSuccess = (message: string) => {
    setSuccessMessage(message)
    // Скрываем сообщение через 3 секунды
    setTimeout(() => setSuccessMessage(null), 3000)
  }

  return (
    <div class={styles['admin-panel']}>
      <header>
        <div class={styles['header-container']}>
          <div class={styles['header-left']}>
            <img src={publyLogo} alt="Logo" class={styles.logo} />
            <h1>
              Панель администратора
              <span class={styles['version-badge']}>v{__APP_VERSION__}</span>
            </h1>
          </div>
          <div class={styles['header-right']}>
            <CommunitySelector />
            <LanguageSwitcher />
            <button class={styles['logout-button']} onClick={handleLogout}>
              Выйти
            </button>
          </div>
        </div>

        <nav class={styles['admin-tabs']}>
          <Button
            variant={currentTab() === 'authors' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/authors')}
          >
            Авторы
          </Button>
          <Button
            variant={currentTab() === 'shouts' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/shouts')}
          >
            Публикации
          </Button>
          <Button
            variant={currentTab() === 'topics' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/topics')}
          >
            Темы
          </Button>
          <Button
            variant={currentTab() === 'communities' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/communities')}
          >
            Сообщества
          </Button>
          <Button
            variant={currentTab() === 'collections' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/collections')}
          >
            Коллекции
          </Button>
          <Button
            variant={currentTab() === 'invites' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/invites')}
          >
            Приглашения
          </Button>
          <Button
            variant={currentTab() === 'env' ? 'primary' : 'secondary'}
            onClick={() => navigate('/admin/env')}
          >
            Переменные среды
          </Button>
        </nav>
      </header>

      <main>
        <Show when={error()}>
          <div class={styles['error-message']}>{error()}</div>
        </Show>

        <Show when={successMessage()}>
          <div class={styles['success-message']}>{successMessage()}</div>
        </Show>

        {/* Используем Show компоненты для каждой вкладки */}
        <Show when={currentTab() === 'authors'}>
          <AuthorsRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>

        <Show when={currentTab() === 'shouts'}>
          <ShoutsRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>

        <Show when={currentTab() === 'topics'}>
          <TopicsRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>

        <Show when={currentTab() === 'communities'}>
          <CommunitiesRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>

        <Show when={currentTab() === 'collections'}>
          <CollectionsRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>

        <Show when={currentTab() === 'invites'}>
          <InvitesRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>

        <Show when={currentTab() === 'env'}>
          <EnvRoute onError={handleError} onSuccess={handleSuccess} />
        </Show>
      </main>
    </div>
  )
}

export default AdminPage
