import { Component, createMemo, createSignal, Show } from 'solid-js'
import { query } from '../graphql'
import { EnvVariable } from '../graphql/generated/schema'
import { ADMIN_UPDATE_ENV_VARIABLE_MUTATION } from '../graphql/mutations'
import formStyles from '../styles/Form.module.css'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import TextPreview from '../ui/TextPreview'

interface EnvVariableModalProps {
  isOpen: boolean
  variable: EnvVariable
  onClose: () => void
  onSave: () => void
  onValueChange?: (value: string) => void // FIXME: no need
}

const EnvVariableModal: Component<EnvVariableModalProps> = (props) => {
  const [value, setValue] = createSignal(props.variable.value)
  const [saving, setSaving] = createSignal(false)
  const [error, setError] = createSignal<string | null>(null)
  const [showFormatted, setShowFormatted] = createSignal(false)

  // Определяем нужно ли использовать textarea
  const needsTextarea = createMemo(() => {
    const val = value()
    return (
      val.length > 50 ||
      val.includes('\n') ||
      props.variable.type === 'json' ||
      props.variable.key.includes('URL') ||
      props.variable.key.includes('SECRET')
    )
  })

  // Форматируем JSON если возможно
  const formattedValue = createMemo(() => {
    if (props.variable.type === 'json' || (value().startsWith('{') && value().endsWith('}'))) {
      try {
        return JSON.stringify(JSON.parse(value()), null, 2)
      } catch {
        return value()
      }
    }
    return value()
  })

  const handleSave = async () => {
    setSaving(true)
    setError(null)

    try {
      const result = await query<{ updateEnvVariable: boolean }>(
        `${location.origin}/graphql`,
        ADMIN_UPDATE_ENV_VARIABLE_MUTATION,
        {
          key: props.variable.key,
          value: value()
        }
      )

      if (result?.updateEnvVariable) {
        props.onSave()
      } else {
        setError('Failed to update environment variable')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred')
    } finally {
      setSaving(false)
    }
  }

  const formatValue = () => {
    if (props.variable.type === 'json') {
      try {
        const formatted = JSON.stringify(JSON.parse(value()), null, 2)
        setValue(formatted)
      } catch (_e) {
        setError('Invalid JSON format')
      }
    }
  }

  return (
    <Modal
      isOpen={props.isOpen}
      title={`Редактировать ${props.variable.key}`}
      onClose={props.onClose}
      size="large"
    >
      <div class={formStyles['modal-wide']}>
        <form class={formStyles.form} onSubmit={(e) => e.preventDefault()}>
          <div class={formStyles['form-group']}>
            <label class={formStyles['form-label']}>Ключ:</label>
            <input
              type="text"
              value={props.variable.key}
              disabled
              class={formStyles['form-input-disabled']}
            />
          </div>

          <div class={formStyles['form-group']}>
            <label class={formStyles['form-label']}>
              Значение:
              <span class={formStyles['form-label-info']}>
                {props.variable.type} {props.variable.isSecret && '(секретное)'}
              </span>
            </label>

            <Show when={needsTextarea()}>
              <div class={formStyles['textarea-container']}>
                <textarea
                  value={value()}
                  onInput={(e) => setValue(e.currentTarget.value)}
                  class={formStyles['form-textarea']}
                  rows={Math.min(Math.max(value().split('\n').length + 2, 4), 15)}
                  placeholder="Введите значение переменной..."
                />
                <Show when={props.variable.type === 'json'}>
                  <div class={formStyles['textarea-actions']}>
                    <Button
                      variant="secondary"
                      size="small"
                      onClick={formatValue}
                      title="Форматировать JSON"
                    >
                      🎨 Форматировать
                    </Button>
                    <Button
                      variant="secondary"
                      size="small"
                      onClick={() => setShowFormatted(!showFormatted())}
                      title={showFormatted() ? 'Скрыть превью' : 'Показать превью'}
                    >
                      {showFormatted() ? '👁️ Скрыть' : '👁️ Превью'}
                    </Button>
                  </div>
                </Show>
              </div>
            </Show>

            <Show when={!needsTextarea()}>
              <input
                type={props.variable.isSecret ? 'password' : 'text'}
                value={value()}
                onInput={(e) => setValue(e.currentTarget.value)}
                class={formStyles['form-input']}
                placeholder="Введите значение переменной..."
              />
            </Show>
          </div>

          <Show when={showFormatted() && (props.variable.type === 'json' || value().startsWith('{'))}>
            <div class={formStyles['form-group']}>
              <label class={formStyles['form-label']}>Превью (форматированное):</label>
              <div class={formStyles['code-preview-container']}>
                <TextPreview content={formattedValue()} />
              </div>
            </div>
          </Show>

          <Show when={props.variable.description}>
            <div class={formStyles['form-help']}>
              <strong>Описание:</strong> {props.variable.description}
            </div>
          </Show>

          <Show when={error()}>
            <div class={formStyles['form-error']}>{error()}</div>
          </Show>

          <div class={formStyles['form-actions']}>
            <Button variant="secondary" onClick={props.onClose} disabled={saving()}>
              Отменить
            </Button>
            <Button variant="primary" onClick={handleSave} loading={saving()}>
              Сохранить
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  )
}

export default EnvVariableModal
