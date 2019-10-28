import { InMemoryCache, NormalizedCacheObject } from "apollo-cache-inmemory";
import { ApolloClient } from "apollo-client";
import { WebSocketLink } from "apollo-link-ws";
import { Server } from "http";
import { AddressInfo } from "net";
import "reflect-metadata"; // tslint:disable-line: no-import-side-effect
import { SubscriptionClient } from "subscriptions-transport-ws";
import ws from "ws";
// tslint:disable-next-line: no-relative-imports
import { startServer } from "../src/startServer";

let serverPort: number;
let expressServer: Server;
const subscriptionClients: SubscriptionClient[] = [];
let subscriptionsPath: string;

export const setupServer = (name: string) => async () => {
  const instance = await startServer({
    port: 0 // random port
  });

  subscriptionsPath = instance.apolloServer.graphqlPath;

  expressServer = instance.expressServer;

  serverPort = (expressServer.address() as AddressInfo).port;
};

export const teardownServer = async () => {
  if (subscriptionClients) {
    for (const subscriptionClient of subscriptionClients) {
      subscriptionClient.close(true, true);
    }
  }

  await Promise.all([
    new Promise(resolve => expressServer && expressServer.close(resolve))
  ]);
};

export const cleanupServer = (name: string) => async () => {};

export const getApolloClient = (authToken?: string) => {
  const websocketUrl = `ws://localhost:${serverPort}${subscriptionsPath}`;

  const subscriptionClient = new SubscriptionClient(
    websocketUrl,
    { reconnect: true },
    ws
  );
  if (authToken) {
    subscriptionClient.use([
      {
        applyMiddleware: async (options, next) => {
          options.authToken = authToken;
          next();
        }
      }
    ]);
  }
  subscriptionClients.push(subscriptionClient);

  const wsLink = new WebSocketLink(subscriptionClient);
  const apolloClient = new ApolloClient({
    link: wsLink,
    cache: new InMemoryCache(),
    defaultOptions: {
      query: {
        fetchPolicy: "no-cache"
      }
    }
  });
  return apolloClient;
};

export type ApolloClient = ApolloClient<NormalizedCacheObject>;

export { serverPort };
