export const ADMIN_LOGIN_MUTATION = `
  mutation AdminLogin($email: String!, $password: String!) {
    login(email: $email, password: $password) {
      success
      token
    }
  }
`

export const ADMIN_LOGOUT_MUTATION = `
  mutation AdminLogout {
    logout {
      success
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
