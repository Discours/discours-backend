import env from "@src/env";
import { AuthChecker } from "type-graphql";

export type User = {
  isAdmin?: boolean;
};

export const authChecker: AuthChecker<{ user: User | undefined }> = (
  { context: { user } },
  roles
) => {
  if (!user) {
    return false;
  }

  if (user.isAdmin) {
    return true;
  }

  if (roles.length === 0) {
    return true;
  }

  if (roles.includes("ADMIN") && user.isAdmin) {
    return true;
  }

  return false;
};

export const getUser = async (apiToken: string) => {
  if (apiToken === env.ADMIN_API_KEY) {
    return {
      isAdmin: true
    };
  }
  return {
    isAdmin: false
  };
};
