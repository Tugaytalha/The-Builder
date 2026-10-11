// The seven services of the bank's service contract (sources/documents/2026-10-01-service-contract.md, sections 4
// and 5). `fields` are the request's `data` fields, all required; `key` says how the test customers file is keyed
// (by customer or by card, `week` adds the requested week); `missing` is the contract's error for a customer or card
// that is not in the file.
const CUSTOMER_NO = { type: "string", description: "The 8-digit customer number from the phone menu (string or number)." };
const CARD_NUMBER = { type: "string", description: "The card number exactly as cards.list returned it (masked, e.g. 540000******1234)." };
const WEEK = { type: "integer", minimum: 1, maximum: 4, description: "The requested statement week, 1 to 4. Not the card's current week." };
const DAY = { type: "integer", description: "The card's current statementDay from statement.week.get." };

const INVALID = { status: 400, code: "INVALID_ARGUMENTS_ERROR", type: "ERROR", message: "Kayıt bulunamadı." };
const notFound = (code, message) => ({ status: 404, code, type: "WARNING", message });

export const SERVICES = {
  "cards.list": {
    summary: "The customer's active cards the assistant may talk about (cardNumber masked, cardNumberLast4, productName, isMainCard), validCardsCount and exitState 1_CARD or MULTI_CARD.",
    fields: { customerNo: CUSTOMER_NO, aiFlow: { type: "string", enum: ["CardOps"], description: "The use case asking. Always CardOps." } },
    required: ["customerNo"],
    key: "customer",
    missing: notFound("FB_IVR_CHANNEL_102", "Müşteriye ait geçerli kart bilgisi bulunamadı."),
  },
  "cards.balance": {
    summary: "The card's last statement date and due date (statementDate, lastPayDate), the next ones, and one debt block per currency (debtTL, debtUSD, debtEUR, debtGBP; a block can be missing) with statementDebt, minPayment, remainingDebt, remainingMinPayment, totalDebt and statementPaymentStatus HAS_DEBT or NO_DEBT.",
    fields: { cardNumber: CARD_NUMBER },
    required: ["cardNumber"],
    key: "card",
    missing: notFound("FB_IVR_CHANNEL_120", "Kart bakiye servisi hatası: kart bulunamadı"),
  },
  "statement.week.get": {
    summary: "The card's current statement week (1-4) and day, its statement and due dates, and the shared statement: relationType empty (own statement), M (main card of a pair) or C (linked card), with relatedCardNumber and relatedCardProductName.",
    fields: { cardNumber: CARD_NUMBER },
    required: ["cardNumber"],
    key: "card",
    missing: notFound("FB_IVR_CHANNEL_121", "Kart bulunamadı."),
  },
  "statement.week.decide": {
    summary: "Preview only, changes nothing: the first statementDate, statementDueDate and statementDay the card would get with the requested week. Do not call it for the card's current week.",
    fields: { cardNumber: CARD_NUMBER, newStatementWeek: WEEK, statementDay: DAY },
    required: ["cardNumber", "newStatementWeek", "statementDay"],
    key: "card",
    week: true,
    missing: INVALID,
  },
  "statement.week.change": {
    summary: "Changes the card's statement week (for a shared statement, both cards). Call only after the caller agreed to the dates from statement.week.decide. Success is exitState OK and responseCode 0.",
    fields: { cardNumber: CARD_NUMBER, newStatementWeek: WEEK, statementDay: DAY },
    required: ["cardNumber", "newStatementWeek", "statementDay"],
    key: "card",
    week: true,
    missing: INVALID,
  },
  "contact.email.get": {
    summary: "The customer's registered contact details. The registered e-mail is ibanEmail; it is empty when there is none (communicationType Phone).",
    fields: { customerNo: CUSTOMER_NO, intAddressInfoType: { type: "string", enum: ["E", "P", "B"], description: "E for e-mail, P for phone, B for both." } },
    required: ["customerNo", "intAddressInfoType"],
    key: "customer",
    missing: INVALID,
  },
  "statement.pdf.send": {
    summary: "Sends the statement PDF to emailAddress. The backend does not check it against the registered address. Success is exitState DONE.",
    fields: {
      customerNo: CUSTOMER_NO,
      cardNumber: CARD_NUMBER,
      currencyType: { type: "string", enum: ["TL", "USD", "EUR", "GBP"], description: "The statement's currency." },
      statementDate: { type: "string", description: "The statementDate from cards.balance (dd.MM.yyyy)." },
      emailAddress: { type: "string", description: "The e-mail address to send to." },
    },
    required: ["customerNo", "cardNumber", "currencyType", "statementDate", "emailAddress"],
    key: "customer",
    missing: notFound("FB_IVR_CHANNEL_107", "Pdf dokümanı bulunamadı"),
  },
};
