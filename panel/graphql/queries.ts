import { gql } from 'graphql-tag'

// Определяем GraphQL запрос
export const ADMIN_GET_SHOUTS_QUERY: string =
  gql`
  query AdminGetShouts($limit: Int, $offset: Int, $search: String, $status: String) {
    adminGetShouts(limit: $limit, offset: $offset, search: $search, status: $status) {
      shouts {
        id
        title
        slug
        body
        lead
        subtitle
        layout
        lang
        cover
        cover_caption
        media {
          url
          title
          body
          source
          pic
        }
        seo
        created_at
        updated_at
        published_at
        featured_at
        deleted_at
        created_by {
          id
          name
          email
          slug
        }
        updated_by {
          id
          name
          email
          slug
        }
        deleted_by {
          id
          name
          email
          slug
        }
        community {
          id
          name
          slug
        }
        authors {
          id
          name
          email
          slug
        }
        topics {
          id
          title
          slug
        }
        version_of
        draft
        stat {
          rating
          comments_count
          viewed
          last_commented_at
        }
      }
      total
      page
      perPage
      totalPages
    }
  }
`.loc?.source.body || ''

export const ADMIN_GET_USERS_QUERY: string =
  gql`
  query AdminGetUsers($limit: Int, $offset: Int, $search: String) {
    adminGetUsers(limit: $limit, offset: $offset, search: $search) {
      authors {
        id
        email
        name
        slug
        roles
        created_at
        last_seen
      }
      total
      page
      perPage
      totalPages
    }
  }
`.loc?.source.body || ''

export const ADMIN_GET_ROLES_QUERY: string =
  gql`
  query AdminGetRoles {
    adminGetRoles {
      id
      name
      description
    }
  }
`.loc?.source.body || ''

export const ADMIN_GET_ENV_VARIABLES_QUERY: string =
  gql`
  query GetEnvVariables {
    getEnvVariables {
      name
      description
      variables {
        key
        value
        description
        type
        isSecret
      }
    }
  }
`.loc?.source.body || ''

export const GET_COMMUNITIES_QUERY: string =
  gql`
  query GetCommunities {
    get_communities_all {
      id
      slug
      name
      desc
      pic
      created_at
      created_by {
        id
        name
        email
        slug
      }
      stat {
        shouts
        followers
        authors
      }
    }
  }
`.loc?.source.body || ''

export const GET_TOPICS_QUERY: string =
  gql`
  query GetTopics {
    get_topics_all {
      id
      slug
      title
      body
      pic
      community
      parent_ids
      stat {
        shouts
        followers
        authors
        comments
      }
      oid
      is_main
    }
  }
`.loc?.source.body || ''

export const GET_COLLECTIONS_QUERY: string =
  gql`
  query GetCollections {
    get_collections_all {
      id
      slug
      title
      desc
      pic
      amount
      published_at
      created_at
      created_by {
        id
        name
        email
        slug
      }
    }
  }
`.loc?.source.body || ''

export const ADMIN_GET_INVITES_QUERY: string =
  gql`
  query AdminGetInvites($limit: Int, $offset: Int, $search: String, $status: String) {
    adminGetInvites(limit: $limit, offset: $offset, search: $search, status: $status) {
      invites {
        inviter_id
        author_id
        shout_id
        status
        inviter {
          id
          name
          email
          slug
        }
        author {
          id
          name
          email
          slug
        }
        shout {
          id
          title
          slug
          created_by {
            id
            name
            email
            slug
          }
        }
        created_at
      }
      total
      page
      perPage
      totalPages
    }
  }
`.loc?.source.body || ''
