import { createEffect, For, Show } from 'solid-js'
import { useData } from '../context/data'
import styles from '../styles/Admin.module.css'

/**
 * Компонент выбора сообщества
 *
 * Особенности:
 * - Сохраняет выбранное сообщество в localStorage
 * - По умолчанию выбрано сообщество с ID 1 (Дискурс)
 * - При изменении автоматически загружает темы выбранного сообщества
 */
const CommunitySelector = () => {
  const { communities, selectedCommunity, setSelectedCommunity, loadTopicsByCommunity, isLoading } =
    useData()

  // Отладочное логирование состояния
  createEffect(() => {
    const current = selectedCommunity()
    const allCommunities = communities()
    console.log('[CommunitySelector] Состояние:', {
      selectedId: current,
      selectedName: allCommunities.find((c) => c.id === current)?.name,
      totalCommunities: allCommunities.length
    })
  })

  // Загружаем темы при изменении выбранного сообщества
  createEffect(() => {
    const communityId = selectedCommunity()
    if (communityId !== null) {
      console.log('[CommunitySelector] Загрузка тем для сообщества:', communityId)
      loadTopicsByCommunity(communityId)
    }
  })

  // Обработчик изменения выбранного сообщества
  const handleCommunityChange = (event: Event) => {
    const select = event.target as HTMLSelectElement
    const value = select.value

    if (value === '') {
      setSelectedCommunity(null)
    } else {
      const communityId = Number.parseInt(value, 10)
      if (!Number.isNaN(communityId)) {
        setSelectedCommunity(communityId)
      }
    }
  }

  return (
    <div class={styles['community-selector']}>
      <select
        id="community-select"
        value={selectedCommunity()?.toString() || ''}
        onChange={handleCommunityChange}
        disabled={isLoading()}
        class={selectedCommunity() !== null ? styles['community-selected'] : ''}
      >
        <option value="">Все сообщества</option>
        <For each={communities()}>
          {(community) => (
            <option value={community.id.toString()}>
              {community.name} {community.id === 1 ? '(По умолчанию)' : ''}
            </option>
          )}
        </For>
      </select>
      <Show when={isLoading()}>
        <span class={styles['loading-indicator']}>Загрузка...</span>
      </Show>
    </div>
  )
}

export default CommunitySelector
