import env from "./env";
import { startServer } from "./startServer";

startServer({
  port: 4000,
  postgresqlUrl: env.POSTGRESQL_URL
}).catch(console.error);
