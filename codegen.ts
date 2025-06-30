import type { CodegenConfig } from '@graphql-codegen/cli'

const config: CodegenConfig = {
  overwrite: true,
  schema: [
    'schema/type.graphql',
    'schema/enum.graphql',
    'schema/input.graphql',
    'schema/mutation.graphql',
    'schema/query.graphql',
    'schema/admin.graphql'
  ],
  documents: ['panel/**/*.{ts,tsx}'],
  generates: {
    './panel/graphql/generated/': {
      preset: 'client',
      plugins: [],
      presetConfig: {
        gqlTagName: 'gql',
        fragmentMasking: false
      }
    },
    './panel/graphql/generated/schema.ts': {
      plugins: ['typescript', 'typescript-resolvers'],
      config: {
        contextType: '../types#GraphQLContext',
        enumsAsTypes: true,
        useIndexSignature: true,
        scalars: {
          DateTime: 'string',
          JSON: '{ [key: string]: any }'
        }
      }
    }
  }
}

export default config
