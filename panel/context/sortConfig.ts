import type {
  AuthorsSortField,
  CollectionsSortField,
  CommunitiesSortField,
  InvitesSortField,
  ShoutsSortField,
  TabSortConfig,
  TopicsSortField
} from './sort'

/**
 * Конфигурации сортировки для разных вкладок админ-панели
 * Основаны на том, что реально поддерживают резолверы в бэкенде
 */

/**
 * Конфигурация сортировки для вкладки "Авторы"
 * Основана на резолвере admin_get_users в resolvers/admin.py
 */
export const AUTHORS_SORT_CONFIG: TabSortConfig = {
  allowedFields: ['id', 'email', 'name', 'created_at', 'last_seen'] as AuthorsSortField[],
  defaultField: 'id' as AuthorsSortField,
  defaultDirection: 'asc'
}

/**
 * Конфигурация сортировки для вкладки "Публикации"
 * Основана на резолвере admin_get_shouts в resolvers/admin.py
 */
export const SHOUTS_SORT_CONFIG: TabSortConfig = {
  allowedFields: ['id', 'title', 'slug', 'created_at', 'published_at', 'updated_at'] as ShoutsSortField[],
  defaultField: 'id' as ShoutsSortField,
  defaultDirection: 'desc' // Новые публикации сначала
}

/**
 * Конфигурация сортировки для вкладки "Темы"
 * Основана на резолвере get_topics_with_stats в resolvers/topic.py
 */
export const TOPICS_SORT_CONFIG: TabSortConfig = {
  allowedFields: [
    'id',
    'title',
    'slug',
    'created_at',
    'authors',
    'shouts',
    'followers'
  ] as TopicsSortField[],
  defaultField: 'id' as TopicsSortField,
  defaultDirection: 'asc'
}

/**
 * Конфигурация сортировки для вкладки "Сообщества"
 * Основана на резолвере get_communities_all в resolvers/community.py
 */
export const COMMUNITIES_SORT_CONFIG: TabSortConfig = {
  allowedFields: [
    'id',
    'name',
    'slug',
    'created_at',
    'created_by',
    'shouts',
    'followers',
    'authors'
  ] as CommunitiesSortField[],
  defaultField: 'id' as CommunitiesSortField,
  defaultDirection: 'asc'
}

/**
 * Конфигурация сортировки для вкладки "Коллекции"
 * Основана на резолвере get_collections_all в resolvers/collection.py
 */
export const COLLECTIONS_SORT_CONFIG: TabSortConfig = {
  allowedFields: ['id', 'title', 'slug', 'created_at', 'published_at'] as CollectionsSortField[],
  defaultField: 'id' as CollectionsSortField,
  defaultDirection: 'asc'
}

/**
 * Конфигурация сортировки для вкладки "Приглашения"
 * Основана на резолвере admin_get_invites в resolvers/admin.py
 */
export const INVITES_SORT_CONFIG: TabSortConfig = {
  allowedFields: ['inviter_name', 'author_name', 'shout_title', 'status'] as InvitesSortField[],
  defaultField: 'inviter_name' as InvitesSortField,
  defaultDirection: 'asc'
}

/**
 * Получает конфигурацию сортировки для указанной вкладки
 */
export const getSortConfigForTab = (tab: string): TabSortConfig => {
  switch (tab) {
    case 'authors':
      return AUTHORS_SORT_CONFIG
    case 'shouts':
      return SHOUTS_SORT_CONFIG
    case 'topics':
      return TOPICS_SORT_CONFIG
    case 'communities':
      return COMMUNITIES_SORT_CONFIG
    case 'collections':
      return COLLECTIONS_SORT_CONFIG
    case 'invites':
      return INVITES_SORT_CONFIG
    default:
      // По умолчанию возвращаем конфигурацию авторов
      return AUTHORS_SORT_CONFIG
  }
}

/**
 * Переводы названий полей для отображения пользователю
 */
export const FIELD_LABELS: Record<string, string> = {
  // Общие поля
  id: 'ID',
  title: 'Название',
  name: 'Имя',
  slug: 'Slug',
  created_at: 'Создано',
  updated_at: 'Обновлено',
  published_at: 'Опубликовано',
  created_by: 'Создатель',
  shouts: 'Публикации',
  followers: 'Подписчики',
  authors: 'Авторы',

  // Поля авторов
  email: 'Email',
  last_seen: 'Последний вход',

  // Поля приглашений
  inviter_name: 'Приглашающий',
  author_name: 'Приглашаемый',
  shout_title: 'Публикация',
  status: 'Статус'
}
