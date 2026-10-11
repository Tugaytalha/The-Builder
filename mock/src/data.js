// The bank's test customers from the case folder. seed() gives a fresh copy for every reset.
const CUSTOMERS = [];

export const seed = () => ({ customers: structuredClone(CUSTOMERS), records: [] });
