import assert from "node:assert/strict";
import { answer } from "../src/fixture.js";
import { SERVICES } from "../src/services.js";

const fx = { customers: [{ customerNo: "1", services: {
  "cards.list": { http: 200, response: { data: { cards: [] } } },
  "cards.balance": { "540000******1234": { http: 200, response: { b: 1 }, delaySeconds: 12 } },
  "statement.week.decide": { "540000******1234": { "2": { http: 500, response: { e: 1 } } } },
} }] };
const call = (name, data) => answer(fx, SERVICES[name], name, data);

assert.deepEqual(call("cards.list", { customerNo: 1 }), { status: 200, data: { data: { cards: [] } }, delay: 0 });
assert.deepEqual(call("cards.balance", { cardNumber: "540000******1234" }), { status: 200, data: { b: 1 }, delay: 12 });
assert.deepEqual(call("statement.week.decide", { cardNumber: "540000******1234", newStatementWeek: "2", statementDay: 5 }).data, { e: 1 });
// the contract's errors: a 404 per service for an unknown customer or card, else a 400
assert.equal(call("cards.list", { customerNo: "9" }).data.result.code, "FB_IVR_CHANNEL_102");
assert.equal(call("cards.balance", { cardNumber: "5400********1234" }).data.result.code, "FB_IVR_CHANNEL_120");
assert.equal(call("statement.week.get", { cardNumber: "x" }).data.result.code, "FB_IVR_CHANNEL_121");
assert.equal(call("statement.pdf.send", { customerNo: "9", cardNumber: "x", currencyType: "TL", statementDate: "1", emailAddress: "a" }).status, 404);
const bad = call("statement.week.decide", { cardNumber: "540000******1234", newStatementWeek: 3, statementDay: 5 });
assert.equal(bad.status, 400);
assert.equal(bad.data.result.code, "INVALID_ARGUMENTS_ERROR");
assert.equal(bad.data.data, undefined);
assert.equal(call("cards.balance", { cardNumber: "" }).data.result.message, "cardNumber cannot be empty");
console.log("fixture ok");
