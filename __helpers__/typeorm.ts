import "reflect-metadata"; // tslint:disable-line: no-import-side-effect
import { Container } from "typedi";
import { createConnection, getConnection, useContainer } from "typeorm";

export const teardownTypeorm = async () => {
  await getConnection().close();
};

export const setupTypeorm = (name: string) => async () => {
  useContainer(Container);
  await createConnection({
    type: "mongodb",
    entities: [`${__dirname}/../../**/+(model|MongoRepository.spec).ts`],
    useNewUrlParser: true
  });
};

export const cleanupTypeorm = (name: string) => async () => {};
