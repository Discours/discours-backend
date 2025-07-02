export const ADMIN_LOGIN_MUTATION = `
  mutation AdminLogin($email: String!, $password: String!) {
    login(email: $email, password: $password) {
      success
      token
      author {
        id
        name
        email
        slug
        roles
      }
      error
    }
  }
`

export const ADMIN_LOGOUT_MUTATION = `
  mutation AdminLogout {
    logout {
      success
      message
    }
  }
`

export const ADMIN_UPDATE_USER_MUTATION = `
  mutation AdminUpdateUser($user: AdminUserUpdateInput!) {
    adminUpdateUser(user: $user) {
      success
      error
    }
  }
`

export const ADMIN_UPDATE_ENV_VARIABLE_MUTATION = `
  mutation AdminUpdateEnvVariable($key: String!, $value: String!) {
    updateEnvVariable(key: $key, value: $value)
  }
`

export const CREATE_TOPIC_MUTATION = `
  mutation CreateTopic($topic_input: TopicInput!) {
    create_topic(topic_input: $topic_input) {
      error
    }
  }
`

export const UPDATE_TOPIC_MUTATION = `
  mutation UpdateTopic($topic_input: TopicInput!) {
    update_topic(topic_input: $topic_input) {
      error
    }
  }
`

export const DELETE_TOPIC_MUTATION = `
  mutation DeleteTopic($id: Int!) {
    delete_topic_by_id(id: $id) {
      error
    }
  }
`

export const CREATE_COMMUNITY_MUTATION = `
  mutation CreateCommunity($community_input: CommunityInput!) {
    create_community(community_input: $community_input) {
      error
    }
  }
`

export const UPDATE_COMMUNITY_MUTATION = `
  mutation UpdateCommunity($community_input: CommunityInput!) {
    update_community(community_input: $community_input) {
      error
    }
  }
`

export const DELETE_COMMUNITY_MUTATION = `
  mutation DeleteCommunity($slug: String!) {
    delete_community(slug: $slug) {
      error
    }
  }
`

export const CREATE_COLLECTION_MUTATION = `
  mutation CreateCollection($collection_input: CollectionInput!) {
    create_collection(collection_input: $collection_input) {
      error
    }
  }
`

export const UPDATE_COLLECTION_MUTATION = `
  mutation UpdateCollection($collection_input: CollectionInput!) {
    update_collection(collection_input: $collection_input) {
      error
    }
  }
`

export const DELETE_COLLECTION_MUTATION = `
  mutation DeleteCollection($slug: String!) {
    delete_collection(slug: $slug) {
      error
    }
  }
`

export const ADMIN_CREATE_INVITE_MUTATION = `
  mutation AdminCreateInvite($invite: AdminInviteUpdateInput!) {
    adminCreateInvite(invite: $invite) {
      success
      error
    }
  }
`

export const ADMIN_UPDATE_INVITE_MUTATION = `
  mutation AdminUpdateInvite($invite: AdminInviteUpdateInput!) {
    adminUpdateInvite(invite: $invite) {
      success
      error
    }
  }
`

export const ADMIN_DELETE_INVITE_MUTATION = `
  mutation AdminDeleteInvite($inviter_id: Int!, $author_id: Int!, $shout_id: Int!) {
    adminDeleteInvite(inviter_id: $inviter_id, author_id: $author_id, shout_id: $shout_id) {
      success
      error
    }
  }
`

export const ADMIN_DELETE_INVITES_BATCH_MUTATION = `
  mutation AdminDeleteInvitesBatch($invites: [AdminInviteIdInput!]!) {
    adminDeleteInvitesBatch(invites: $invites) {
      success
      error
    }
  }
`

export const MERGE_TOPICS_MUTATION = `
  mutation MergeTopics($merge_input: TopicMergeInput!) {
    merge_topics(merge_input: $merge_input) {
      error
      message
      topic {
        id
        title
        slug
      }
      stats
    }
  }
`

export const SET_TOPIC_PARENT_MUTATION = `
  mutation SetTopicParent($topic_id: Int!, $parent_id: Int) {
    set_topic_parent(topic_id: $topic_id, parent_id: $parent_id) {
      error
      message
      topic {
        id
        title
        slug
        parent_ids
      }
    }
  }
`
