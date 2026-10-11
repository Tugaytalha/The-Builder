import assert from "node:assert/strict";
import { answer } from "../src/fixture.js";

const fx = { customers: [{ customerNo: "1", services: {
  "cards.list": { http: 200, response: { data: { cards: [] } } },
  "cards.balance": { "540000******1234": { http: 200, response: { b: 1 } }, "540000******9234": { http: 200, response: { b: 2 } } },
  "statement.week.decide": { "540000******1234": { "2": { http: 500, response: { e: 1 } } } },
} }] };
const card = { customer: "customerNo", card: "cardNumber" };
const week = { ...card, week: "newStatementWeek" };

assert.deepEqual(answer(fx, "cards.list", { customer: "customerNo" }, { customerNo: "1" }), { status: 200, data: { data: { cards: [] } } });
assert.deepEqual(answer(fx, "cards.balance", card, { customerNo: "1", cardNumber: "540000******1234" }).data, { b: 1 });
// another mask of the same card, or only the digits the customer said, when they name one card
assert.deepEqual(answer(fx, "cards.balance", card, { customerNo: "1", cardNumber: "5400********9234" }).data, { b: 2 });
assert.equal(answer(fx, "cards.balance", card, { customerNo: "1", cardNumber: "234" }).status, 404);
assert.deepEqual(answer(fx, "statement.week.decide", week, { customerNo: "1", cardNumber: "540000******1234", newStatementWeek: 2 }), { status: 500, data: { e: 1 } });
assert.equal(answer(fx, "cards.list", { customer: "customerNo" }, { customerNo: "9" }).status, 404);
assert.equal(answer(fx, "statement.week.decide", week, { customerNo: "1", cardNumber: "540000******1234", newStatementWeek: 3 }).status, 404);
console.log("fixture ok");
