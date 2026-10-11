import assert from "node:assert/strict";
import { match } from "../src/match.js";

const routes = { "GET /customers/{customerNumber}/cards": "cards", "POST /ping": "ping" };
assert.deepEqual(match(routes, "GET", "/customers/12345678/cards"), { route: "cards", params: { customerNumber: "12345678" } });
assert.deepEqual(match(routes, "POST", "/ping"), { route: "ping", params: {} });
assert.equal(match(routes, "POST", "/customers/1/cards"), null);
assert.equal(match(routes, "GET", "/customers/1/cards/x"), null);
console.log("match ok");
