// One route per service of the service contract: POST /voice/v1/<service>. The answers come from src/test-customers.json,
// a copy of the case's test-environment/test-customers.json.
import FIXTURE from "./test-customers.json";
import { SERVICES } from "./services.js";
import { answer } from "./fixture.js";

export const BASE = "/voice/v1/";

export const ROUTES = Object.fromEntries(
  Object.entries(SERVICES).map(([name, spec]) => [`POST ${BASE}${name}`, (data) => answer(FIXTURE, spec, name, data)]),
);
