import { createContext, createEffect, createSignal, JSX, onMount, useContext } from 'solid-js'
import {
  ADMIN_GET_ROLES_QUERY,
  ADMIN_GET_TOPICS_QUERY,
  GET_COMMUNITIES_QUERY,
  GET_TOPICS_BY_COMMUNITY_QUERY,
  GET_TOPICS_QUERY
} from '../graphql/queries'

export interface Community {
  id: number
  name: string
  slug: string
  desc?: string
  pic?: string
}

export interface Topic {
  id: number
  slug: string
  title: string
  body?: string
  pic?: string
  community: number
  parent_ids?: number[]
}

export interface Role {
  id: string
  name: string
  description?: string
}

interface DataContextType {
  // Сообщества
  communities: () => Community[]
  getCommunityById: (id: number) => Community | undefined
  getCommunityName: (id: number) => string
  selectedCommunity: () => number | null
  setSelectedCommunity: (id: number | null) => void

  // Топики
  topics: () => Topic[]
  allTopics: () => Topic[]
  getTopicById: (id: number) => Topic | undefined
  getTopicTitle: (id: number) => string
  loadTopicsByCommunity: (communityId: number) => Promise<Topic[]>

  // Роли
  roles: () => Role[]
  getRoleById: (id: string) => Role | undefined
  getRoleName: (id: string) => string

  // Общие методы
  isLoading: () => boolean
  loadData: () => Promise<void>
  // biome-ignore lint/suspicious/noExplicitAny: grahphql
  queryGraphQL: (query: string, variables?: Record<string, any>) => Promise<any>
}

const DataContext = createContext<DataContextType>({
  // Сообщества
  communities: () => [],
  getCommunityById: () => undefined,
  getCommunityName: () => '',
  selectedCommunity: () => null,
  setSelectedCommunity: () => {},

  // Топики
  topics: () => [],
  allTopics: () => [],
  getTopicById: () => undefined,
  getTopicTitle: () => '',
  loadTopicsByCommunity: async () => [],

  // Роли
  roles: () => [],
  getRoleById: () => undefined,
  getRoleName: () => '',

  // Общие методы
  isLoading: () => false,
  loadData: async () => {},
  queryGraphQL: async () => {}
})

/**
 * Ключ для сохранения выбранного сообщества в localStorage
 */
const COMMUNITY_STORAGE_KEY = 'admin-selected-community'

export function DataProvider(props: { children: JSX.Element }) {
  const [communities, setCommunities] = createSignal<Community[]>([])
  const [topics, setTopics] = createSignal<Topic[]>([])
  const [allTopics, setAllTopics] = createSignal<Topic[]>([])
  const [roles, setRoles] = createSignal<Role[]>([])

  // Инициализация выбранного сообщества из localStorage
  const initialCommunity = (() => {
    try {
      const stored = localStorage.getItem(COMMUNITY_STORAGE_KEY)
      if (stored) {
        const communityId = Number.parseInt(stored, 10)
        return Number.isNaN(communityId) ? 1 : communityId
      }
    } catch (e) {
      console.warn('[DataProvider] Ошибка при чтении сообщества из localStorage:', e)
    }
    return 1 // По умолчанию выбираем сообщество с ID 1 (Дискурс)
  })()

  const [selectedCommunity, setSelectedCommunity] = createSignal<number | null>(initialCommunity)
  const [isLoading, setIsLoading] = createSignal(false)

  // Сохранение выбранного сообщества в localStorage
  const updateSelectedCommunity = (id: number | null) => {
    try {
      if (id !== null) {
        localStorage.setItem(COMMUNITY_STORAGE_KEY, id.toString())
        console.log('[DataProvider] Сохранено сообщество в localStorage:', id)
      } else {
        localStorage.removeItem(COMMUNITY_STORAGE_KEY)
        console.log('[DataProvider] Удалено сохраненное сообщество из localStorage')
      }
      setSelectedCommunity(id)
    } catch (e) {
      console.error('[DataProvider] Ошибка при сохранении сообщества в localStorage:', e)
      setSelectedCommunity(id) // Всё равно обновляем состояние
    }
  }

  // Эффект для загрузки ролей при изменении сообщества
  createEffect(() => {
    const community = selectedCommunity()
    if (community !== null) {
      console.log('[DataProvider] Загрузка ролей для сообщества:', community)
      loadRoles(community).catch((err) => {
        console.warn('Не удалось загрузить роли для сообщества:', err)
      })
    }
  })

  // Загрузка данных при монтировании
  onMount(() => {
    console.log('[DataProvider] Инициализация с сообществом:', initialCommunity)
    loadData().catch((err) => {
      console.error('Ошибка при начальной загрузке данных:', err)
    })
  })

  // Загрузка сообществ
  const loadCommunities = async () => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: GET_COMMUNITIES_QUERY
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const communitiesData = result.data.get_communities_all || []
      setCommunities(communitiesData)
      return communitiesData
    } catch (error) {
      console.error('Ошибка загрузки сообществ:', error)
      return []
    }
  }

  // Загрузка всех топиков
  const loadTopics = async () => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: GET_TOPICS_QUERY
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const topicsData = result.data.get_topics_all || []
      setTopics(topicsData)
      return topicsData
    } catch (error) {
      console.error('Ошибка загрузки топиков:', error)
      return []
    }
  }

  // Загрузка всех топиков сообщества
  const loadTopicsByCommunity = async (communityId: number) => {
    try {
      setIsLoading(true)

      // Используем админский резолвер для получения всех топиков без лимитов
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: ADMIN_GET_TOPICS_QUERY,
          variables: {
            community_id: communityId
          }
        })
      })

      const result = await response.json()

      if (result.errors) {
        throw new Error(result.errors[0].message)
      }

      const allTopicsData = result.data.adminGetTopics || []

      // Сохраняем все данные сразу для отображения
      setTopics(allTopicsData)
      setAllTopics(allTopicsData)

      console.log(`[DataProvider] Загружено ${allTopicsData.length} топиков для сообщества ${communityId}`)
      return allTopicsData
    } catch (error) {
      console.error('Ошибка загрузки топиков по сообществу:', error)
      return []
    } finally {
      setIsLoading(false)
    }
  }

  // Загрузка ролей для конкретного сообщества
  const loadRoles = async (communityId?: number) => {
    try {
      console.log(
        '[DataProvider] Загружаем роли...',
        communityId ? `для сообщества ${communityId}` : 'все роли'
      )

      const variables = communityId ? { community: communityId } : {}

      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: ADMIN_GET_ROLES_QUERY,
          variables
        })
      })

      const result = await response.json()
      console.log('[DataProvider] Ответ от сервера для ролей:', result)

      if (result.errors) {
        console.warn('Не удалось загрузить роли (возможно не авторизован):', result.errors[0].message)
        setRoles([])
        return []
      }

      const rolesData = result.data.adminGetRoles || []
      console.log('[DataProvider] Роли успешно загружены:', rolesData)
      setRoles(rolesData)
      return rolesData
    } catch (error) {
      console.warn('Ошибка загрузки ролей:', error)
      setRoles([])
      return []
    }
  }

  // Загрузка всех данных
  const loadData = async () => {
    setIsLoading(true)
    try {
      // Загружаем все данные сразу (вызывается только для авторизованных пользователей)
      // Роли загружаем в фоне - их отсутствие не должно блокировать интерфейс
      await Promise.all([
        loadCommunities(),
        loadTopics(),
        loadRoles(selectedCommunity() || undefined).catch((err) => {
          console.warn('Роли недоступны (возможно не хватает прав):', err)
          return []
        })
      ])

      // selectedCommunity теперь всегда инициализировано со значением 1,
      // поэтому дополнительная проверка не нужна
    } catch (error) {
      console.error('Ошибка загрузки данных:', error)
    } finally {
      setIsLoading(false)
    }
  }

  // Методы для работы с сообществами
  const getCommunityById = (id: number): Community | undefined => {
    return communities().find((community) => community.id === id)
  }

  const getCommunityName = (id: number): string => getCommunityById(id)?.name || ''
  const getTopicTitle = (id: number): string => getTopicById(id)?.title || ''

  // Методы для работы с топиками
  const getTopicById = (id: number): Topic | undefined => {
    return topics().find((topic) => topic.id === id)
  }

  // Методы для работы с ролями
  const getRoleById = (id: string): Role | undefined => {
    return roles().find((role) => role.id === id)
  }

  const getRoleName = (id: string): string => {
    const role = getRoleById(id)
    return role ? role.name : id
  }

  const value = {
    // Сообщества
    communities,
    getCommunityById,
    getCommunityName,
    selectedCommunity,
    setSelectedCommunity: updateSelectedCommunity,

    // Топики
    topics,
    allTopics,
    getTopicById,
    getTopicTitle,
    loadTopicsByCommunity,

    // Роли
    roles,
    getRoleById,
    getRoleName,

    // Общие методы
    isLoading,
    loadData,
    // biome-ignore lint/suspicious/noExplicitAny: grahphql
    queryGraphQL: async (query: string, variables?: Record<string, any>) => {
      try {
        const response = await fetch('/graphql', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            query,
            variables
          })
        })

        const result = await response.json()

        if (result.errors) {
          throw new Error(result.errors[0].message)
        }

        return result.data
      } catch (error) {
        console.error('Ошибка выполнения GraphQL запроса:', error)
        return null
      }
    }
  }

  return <DataContext.Provider value={value}>{props.children}</DataContext.Provider>
}

export const useData = () => useContext(DataContext)
