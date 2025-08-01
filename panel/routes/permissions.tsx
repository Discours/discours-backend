/**
 * Компонент для управления правами в админ-панели
 * @module PermissionsRoute
 */

import { Component, createSignal } from 'solid-js'
import { ADMIN_UPDATE_PERMISSIONS_MUTATION } from '../graphql/mutations'
import { query } from '../graphql'
import Button from '../ui/Button'
import styles from '../styles/Admin.module.css'

/**
 * Интерфейс свойств компонента PermissionsRoute
 */
export interface PermissionsRouteProps {
  onError: (error: string) => void
  onSuccess: (message: string) => void
}

/**
 * Компонент для управления правами
 */
const PermissionsRoute: Component<PermissionsRouteProps> = (props) => {
  const [isUpdating, setIsUpdating] = createSignal(false)

  /**
   * Обновляет права для всех сообществ
   */
  const handleUpdatePermissions = async () => {
    if (isUpdating()) return

    setIsUpdating(true)
    try {
      const response = await query<{
        adminUpdatePermissions: { success: boolean; error?: string; message?: string }
      }>(`${location.origin}/graphql`, ADMIN_UPDATE_PERMISSIONS_MUTATION)

      if (response?.adminUpdatePermissions?.success) {
        props.onSuccess('Права для всех сообществ успешно обновлены')
      } else {
        const error = response?.adminUpdatePermissions?.error || 'Неизвестная ошибка'
        props.onError(`Ошибка обновления прав: ${error}`)
      }
    } catch (error) {
      props.onError(`Ошибка запроса: ${(error as Error).message}`)
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <div class={styles['permissions-section']}>
      <div class={styles['section-header']}>
        <h2>Управление правами</h2>
        <p>Обновление прав для всех сообществ с новыми дефолтными настройками</p>
      </div>

      <div class={styles['permissions-content']}>
        <div class={styles['permissions-info']}>
          <h3>Что делает обновление прав?</h3>
          <ul>
            <li>Обновляет права для всех существующих сообществ</li>
            <li>Применяет новую иерархию ролей</li>
            <li>Синхронизирует права с файлом default_role_permissions.json</li>
            <li>Удаляет старые права и инициализирует новые</li>
          </ul>

          <div class={styles['warning-box']}>
            <strong>⚠️ Внимание:</strong> Эта операция затрагивает все сообщества в системе.
            Рекомендуется выполнять только при изменении системы прав.
          </div>
        </div>

        <div class={styles['permissions-actions']}>
          <Button
            variant="primary"
            onClick={handleUpdatePermissions}
            disabled={isUpdating()}
            loading={isUpdating()}
          >
            {isUpdating() ? 'Обновление...' : 'Обновить права для всех сообществ'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default PermissionsRoute
