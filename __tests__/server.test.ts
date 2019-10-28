import { serverPort, setupServer, teardownServer } from "__helpers__/server";
import nodeFetch from "node-fetch";

beforeAll(setupServer("serverTest"));
afterAll(teardownServer);

it("should start the server", async () => {
  // tslint:disable-next-line: no-http-string
  const response = await nodeFetch(`http://localhost:${serverPort}/`);
  expect(response.status).toBe(200);
});
