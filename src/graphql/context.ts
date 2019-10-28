import { Context } from "apollo-server-core";
import { User } from "./auth";

export type AppContext = Context<{ user: User }>;
