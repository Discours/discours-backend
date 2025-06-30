import { Component, JSX, Show } from 'solid-js'
import styles from '../styles/Modal.module.css'

export interface ModalProps {
  title: string
  isOpen: boolean
  onClose: () => void
  children: JSX.Element
  footer?: JSX.Element
  size?: 'small' | 'medium' | 'large'
}

const Modal: Component<ModalProps> = (props) => {
  const handleBackdropClick = (e: MouseEvent) => {
    if (e.target === e.currentTarget) {
      props.onClose()
    }
  }

  const modalClasses = () => {
    const baseClass = styles.modal
    const sizeClass = styles[`modal-${props.size || 'medium'}`]
    return [baseClass, sizeClass].join(' ')
  }

  return (
    <Show when={props.isOpen}>
      <div class={styles.backdrop} onClick={handleBackdropClick}>
        <div class={modalClasses()}>
          <div class={styles.header}>
            <h2 class={styles.title}>{props.title}</h2>
            <button class={styles.close} onClick={props.onClose}>
              ×
            </button>
          </div>

          <div class={styles.content}>{props.children}</div>

          <Show when={props.footer}>
            <div class={styles.footer}>{props.footer}</div>
          </Show>
        </div>
      </div>
    </Show>
  )
}

export default Modal
