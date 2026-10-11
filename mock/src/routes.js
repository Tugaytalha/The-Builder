// One route per bank service. Each answer comes from the test customers file (src/test-customers.json, a copy of the
// case's test-environment file). TODO: the paths and request field names come from the service contract (section 6).
import FIXTURE from "./test-customers.json";
import { answer } from "./fixture.js";

const CUSTOMER = { customer: "customerNo" };
const CARD = { ...CUSTOMER, card: "cardNumber" };
const WEEK = { ...CARD, week: "newStatementWeek" };

export const SERVICES = [
  { service: "cards.list", route: "POST /cards/list", keys: CUSTOMER },
  { service: "cards.balance", route: "POST /cards/balance", keys: CARD },
  { service: "statement.week.get", route: "POST /statement/week/get", keys: CARD },
  { service: "statement.week.decide", route: "POST /statement/week/decide", keys: WEEK },
  { service: "statement.week.change", route: "POST /statement/week/change", keys: WEEK },
  { service: "contact.email.get", route: "POST /contact/email/get", keys: CUSTOMER },
  { service: "statement.pdf.send", route: "POST /statement/pdf/send", keys: CARD },
];

export const ROUTES = Object.fromEntries(
  SERVICES.map(({ service, route, keys }) => [route, (state, body) => answer(FIXTURE, service, keys, body)]),
);
