// Answers a service call from the test customers file, as section 6 of the service contract says: the listed status
// and body for a known customer or card, the service's `missing` error otherwise, and a 400 for an empty field.
const error = ({ status, code, type, message }) => ({
  status,
  data: { result: { guid: crypto.randomUUID().replaceAll("-", ""), returnCode: code, messageText: message, code, message, type, details: { guid: null, rootCause: null, errorOrigin: "the-builder-mock" } } },
  delay: 0,
});

// The file entry for this call: customers[].services[name], keyed by customer number, or by card number for the card
// services (card numbers are unique across customers), then by the requested week.
function entry(fixture, spec, name, data) {
  if (spec.key === "customer") return fixture.customers.find((c) => c.customerNo === String(data.customerNo))?.services[name];
  for (const c of fixture.customers) {
    const byCard = c.services[name]?.[data.cardNumber];
    if (byCard) return spec.week ? byCard[String(data.newStatementWeek)] : byCard;
  }
}

export function answer(fixture, spec, name, data) {
  for (const field of spec.required)
    if (data[field] === undefined || data[field] === null || String(data[field]).trim() === "")
      return error({ status: 400, code: "INVALID_ARGUMENTS_ERROR", type: "ERROR", message: `${field} cannot be empty` });
  const found = entry(fixture, spec, name, data);
  if (!found) return error(spec.missing);
  return { status: found.http, data: found.response, delay: found.delaySeconds ?? 0 };
}
