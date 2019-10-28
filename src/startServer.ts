import "module-alias/register"; // tslint:disable-line: no-import-side-effect
import "reflect-metadata"; // tslint:disable-line: no-import-side-effect

import { authChecker, getUser } from "@src/graphql/auth";
import resolvers from "@src/graphql/resolvers";
import { ApolloServer } from "apollo-server-express";
import cors from "cors";
import express from "express";
import { buildSchema } from "type-graphql";
import { Container } from "typedi";
import { createConnection, useContainer } from "typeorm";

interface IBootstrapOptions {
  port: number;
  postgresqlUrl: string;
  onServerStart?(): void;
}

useContainer(Container);

export async function startServer(options: IBootstrapOptions) {
  await createConnection({
    type: "postgres",
    entities: [`${__dirname}/**/model.ts`],
    url: options.postgresqlUrl,
    migrations: ["src/migration/**/*.ts"]
  });

  const schema = await buildSchema({
    resolvers: resolvers,
    container: Container,
    authChecker: authChecker
  });

  const apolloServer = new ApolloServer({
    schema,
    playground: true,
    subscriptions: "/graphql",
    introspection: true,
    context: async ({ req, payload }: ApolloContext) => {
      const apiToken =
        (payload && payload.authToken) ||
        ((req && req.headers.authorization) || "").replace("Bearer ", "");
      const user = await getUser(apiToken);
      return { user };
    }
  });
  const app = express();
  app.use(cors());
  app.get("/", (req, res) => {
    return res.status(200).json({});
  });
  apolloServer.applyMiddleware({ app, path: "/graphql" });
  const expressServer = app.listen({ port: options.port });
  apolloServer.installSubscriptionHandlers(expressServer);

  if (options.port) {
    // tslint:disable-next-line: no-console
    console.log(`Server listens on :${options.port}`);
  }
  return { apolloServer, expressServer, expressApp: app };
}

type ApolloContext = {
  req: { headers: { [key: string]: string | undefined } };
  payload: { [key: string]: string | undefined };
};
