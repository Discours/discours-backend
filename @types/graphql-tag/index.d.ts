import { DocumentNode } from "graphql";

declare module "graphql-tag" {
  export default function gql(
    literals: unknown,
    ...placeholders: unknown[]
  ): DocumentNode;
  export function resetCaches(): void;
  export function disableFragmentWarnings(): void;
}
