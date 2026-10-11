// Answers a service call from the test customers file: customers[].services[service], then the card key, then the
// week key. `keys` names the request fields that hold the customer, the card and the week.
const notFound = (message) => ({
  status: 404,
  data: { result: { returnCode: "FB_IVR_CHANNEL_404", messageText: message, code: "FB_IVR_CHANNEL_404", message, type: "WARNING" } },
});

const digits = (s) => String(s ?? "").replace(/\D/g, "");

// The card's key in the file. A different mask of the same card ("5400********1234" for "540000******1234") or only
// its last digits also finds it, when exactly one card ends with those digits.
function cardKey(entries, value) {
  if (value in entries) return value;
  const want = digits(value).slice(-4);
  if (want.length < 4) return null;
  const hits = Object.keys(entries).filter((k) => digits(k).endsWith(want));
  return hits.length === 1 ? hits[0] : null;
}

export function answer(fixture, service, keys, body) {
  const customer = fixture.customers.find((c) => c.customerNo === String(body[keys.customer] ?? ""));
  if (!customer) return notFound("Müşteri bulunamadı.");
  let entry = customer.services[service];
  if (!entry) return notFound("Kayıt bulunamadı.");
  if (keys.card) {
    const key = cardKey(entry, body[keys.card]);
    if (!key) return notFound("Kart bulunamadı.");
    entry = entry[key];
  }
  if (keys.week) {
    entry = entry[String(body[keys.week] ?? "")];
    if (!entry) return notFound("Kayıt bulunamadı.");
  }
  return { status: entry.http, data: entry.response };
}
