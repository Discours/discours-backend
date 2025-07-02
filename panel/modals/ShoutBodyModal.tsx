import { Component, For } from 'solid-js'
import type { AdminShoutInfo, Maybe, Topic } from '../graphql/generated/schema'
import styles from '../styles/Modal.module.css'
import CodePreview from '../ui/CodePreview'
import Modal from '../ui/Modal'

export interface ShoutBodyModalProps {
  shout: AdminShoutInfo
  isOpen: boolean
  onClose: () => void
}

const ShoutBodyModal: Component<ShoutBodyModalProps> = (props) => {
  return (
    <Modal
      title={`Просмотр публикации: ${props.shout.title}`}
      isOpen={props.isOpen}
      onClose={props.onClose}
      size="large"
    >
      <div class={styles['shout-body']}>
        <div class={styles['shout-info']}>
          <div class={styles['info-row']}>
            <span class={styles['info-label']}>Автор:</span>
            <span class={styles['info-value']}>{props.shout?.authors?.[0]?.email}</span>
          </div>
          <div class={styles['info-row']}>
            <span class={styles['info-label']}>Просмотры:</span>
            <span class={styles['info-value']}>{props.shout.stat?.viewed || 0}</span>
          </div>
          <div class={styles['info-row']}>
            <span class={styles['info-label']}>Темы:</span>
            <div class={styles['topics-list']}>
              <For each={props.shout?.topics}>
                {(topic: Maybe<Topic>) => <span class={styles['topic-badge']}>{topic?.title || ''}</span>}
              </For>
            </div>
          </div>
        </div>

        <div class={styles['shout-content']}>
          <h3>Содержание</h3>
          <div class={styles['content-preview']}>
            <CodePreview content={props.shout.body || ''} maxHeight="85vh" language="html" autoFormat />
          </div>
        </div>
      </div>
    </Modal>
  )
}

export default ShoutBodyModal
