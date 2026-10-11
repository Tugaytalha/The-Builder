// One handler per route of the service contract: (state, body) => { status, data }. Change `state` in place to record.
export const ROUTES = {
  "POST /ping": (state, body) => ({ data: { ok: true, echo: body, customers: state.customers.length } }),
};
