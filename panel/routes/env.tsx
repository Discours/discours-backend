import { Component, createSignal, For, Show } from 'solid-js'
import { query } from '../graphql'
import type { EnvSection, EnvVariable, Query } from '../graphql/generated/schema'
import { ADMIN_UPDATE_ENV_VARIABLE_MUTATION } from '../graphql/mutations'
import { ADMIN_GET_ENV_VARIABLES_QUERY } from '../graphql/queries'
import EnvVariableModal from '../modals/EnvVariableModal'
import styles from '../styles/Admin.module.css'
import Button from '../ui/Button'

export interface EnvRouteProps {
  onError?: (error: string) => void
  onSuccess?: (message: string) => void
}

const EnvRoute: Component<EnvRouteProps> = (props) => {
  const [envSections, setEnvSections] = createSignal<EnvSection[]>([])
  const [loading, setLoading] = createSignal(true)
  const [editingVariable, setEditingVariable] = createSignal<EnvVariable | null>(null)
  const [showVariableModal, setShowVariableModal] = createSignal(false)

  // Состояние для показа/скрытия значений
  const [shownVars, setShownVars] = createSignal<{ [key: string]: boolean }>({})

  /**
   * Загружает переменные окружения
   */
  const loadEnvVariables = async () => {
    try {
      setLoading(true)
      const result = await query<{ getEnvVariables: Query['getEnvVariables'] }>(
        `${location.origin}/graphql`,
        ADMIN_GET_ENV_VARIABLES_QUERY
      )

      // Важно: пустой массив [] тоже валидный результат!
      if (result && Array.isArray(result.getEnvVariables)) {
        setEnvSections(result.getEnvVariables)
        console.log('Загружено секций переменных:', result.getEnvVariables.length)
      } else {
        console.warn('Неожиданный результат от getEnvVariables:', result)
        setEnvSections([]) // Устанавливаем пустой массив если что-то пошло не так
      }
    } catch (error) {
      console.error('Failed to load env variables:', error)
      props.onError?.(error instanceof Error ? error.message : 'Failed to load environment variables')
      setEnvSections([]) // Устанавливаем пустой массив при ошибке
    } finally {
      setLoading(false)
    }
  }

  /**
   * Обновляет значение переменной окружения
   */
  const updateEnvVariable = async (key: string, value: string) => {
    try {
      const result = await query(`${location.origin}/graphql`, ADMIN_UPDATE_ENV_VARIABLE_MUTATION, {
        key,
        value
      })

      if (result && typeof result === 'object' && 'updateEnvVariable' in result) {
        props.onSuccess?.(`Переменная ${key} успешно обновлена`)
        await loadEnvVariables()
      } else {
        props.onError?.('Не удалось обновить переменную')
      }
    } catch (err) {
      console.error('Ошибка обновления переменной:', err)
      props.onError?.(err instanceof Error ? err.message : 'Ошибка при обновлении переменной')
    }
  }

  /**
   * Обработчик открытия модального окна редактирования переменной
   */
  const openVariableModal = (variable: EnvVariable) => {
    setEditingVariable({ ...variable })
    setShowVariableModal(true)
  }

  /**
   * Обработчик закрытия модального окна редактирования переменной
   */
  const closeVariableModal = () => {
    setEditingVariable(null)
    setShowVariableModal(false)
  }

  /**
   * Обработчик сохранения переменной
   */
  const saveVariable = async () => {
    const variable = editingVariable()
    if (!variable) return

    await updateEnvVariable(variable.key, variable.value)
    closeVariableModal()
  }

  /**
   * Обработчик изменения значения в модальном окне
   */
  const handleVariableValueChange = (value: string) => {
    const variable = editingVariable()
    if (variable) {
      setEditingVariable({ ...variable, value })
    }
  }

  /**
   * Переключает показ значения переменной
   */
  const toggleShow = (key: string) => {
    setShownVars((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  /**
   * Копирует значение в буфер обмена
   */
  const CopyButton: Component<{ value: string }> = (props) => {
    const handleCopy = async (e: MouseEvent) => {
      e.preventDefault()
      try {
        await navigator.clipboard.writeText(props.value)
        // Можно добавить всплывающее уведомление
      } catch (err) {
        alert(`Ошибка копирования: ${(err as Error).message}`)
      }
    }
    return (
      <a class="btn" title="Скопировать" type="button" style="margin-left: 6px" onClick={handleCopy}>
        📋
      </a>
    )
  }

  /**
   * Кнопка показать/скрыть значение переменной
   */
  const ShowHideButton: Component<{ shown: boolean; onToggle: () => void }> = (props) => {
    return (
      <a
        class="btn"
        title={props.shown ? 'Скрыть' : 'Показать'}
        type="button"
        style="margin-left: 6px"
        onClick={props.onToggle}
      >
        {props.shown ? '🙈' : '👁️'}
      </a>
    )
  }

  // Load env variables on mount
  void loadEnvVariables()

  // ВРЕМЕННО: для тестирования пустого состояния
  // setTimeout(() => {
  //   setLoading(false)
  //   setEnvSections([])
  //   console.log('Тест: установлено пустое состояние')
  // }, 1000)

  return (
    <div class={styles['env-variables-container']}>
      <Show when={loading()}>
        <div class={styles['loading']}>Загрузка переменных окружения...</div>
      </Show>

      <Show when={!loading() && envSections().length === 0}>
        <div class={styles['empty-state']}>
          <h3>Переменные окружения не найдены</h3>
          <p>
            Переменные окружения не настроены или не обнаружены в системе.
            <br />
            Вы можете добавить переменные через файл <code>.env</code> или системные переменные.
          </p>
          <details style="margin-top: 16px;">
            <summary style="cursor: pointer; font-weight: 600;">Как добавить переменные?</summary>
            <div style="margin-top: 8px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
              <p>
                <strong>Способ 1:</strong> Через командную строку
              </p>
              <pre style="background: #e9ecef; padding: 8px; border-radius: 4px; font-size: 12px;">
                export DEBUG=true export DB_URL="postgresql://localhost:5432/db" export
                REDIS_URL="redis://localhost:6379"
              </pre>

              <p style="margin-top: 12px;">
                <strong>Способ 2:</strong> Через файл .env
              </p>
              <pre style="background: #e9ecef; padding: 8px; border-radius: 4px; font-size: 12px;">
                DEBUG=true DB_URL=postgresql://localhost:5432/db REDIS_URL=redis://localhost:6379
              </pre>
            </div>
          </details>
        </div>
      </Show>

      <Show when={!loading() && envSections().length > 0}>
        <div class={styles['env-sections']}>
          <For each={envSections()}>
            {(section) => (
              <div class={styles['env-section']}>
                <h3 class={styles['section-name']}>{section.name}</h3>
                <Show when={section.description}>
                  <p class={styles['section-description']}>{section.description}</p>
                </Show>
                <div class={styles['variables-list']}>
                  <table>
                    <thead>
                      <tr>
                        <th>Ключ</th>
                        <th>Значение</th>
                        <th>Описание</th>
                        <th>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      <For each={section.variables}>
                        {(variable) => {
                          const shown = () => shownVars()[variable.key] || false
                          return (
                            <tr>
                              <td>{variable.key}</td>
                              <td>
                                {variable.isSecret && !shown()
                                  ? '••••••••'
                                  : variable.value || <span class={styles['empty-value']}>не задано</span>}
                                <CopyButton value={variable.value || ''} />
                                {variable.isSecret && (
                                  <ShowHideButton
                                    shown={shown()}
                                    onToggle={() => toggleShow(variable.key)}
                                  />
                                )}
                              </td>
                              <td>{variable.description || '-'}</td>
                              <td class={styles['actions']}>
                                <Button
                                  variant="secondary"
                                  size="small"
                                  onClick={() => openVariableModal(variable)}
                                >
                                  Изменить
                                </Button>
                              </td>
                            </tr>
                          )
                        }}
                      </For>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show when={editingVariable()}>
        <EnvVariableModal
          isOpen={showVariableModal()}
          variable={editingVariable()!}
          onClose={closeVariableModal}
          onSave={saveVariable}
          onValueChange={handleVariableValueChange}
        />
      </Show>
    </div>
  )
}

export default EnvRoute
