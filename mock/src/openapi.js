// The tool API the phone agent gets: one operation per route in src/routes.js, with the contract's field names.
// The Worker adds `servers` with its own address.
export const OPENAPI = {
  openapi: "3.0.0",
  info: { title: "Bank mock", version: "1" },
  paths: {
    "/ping": {
      post: {
        operationId: "ping",
        summary: "Check that the mock answers.",
        requestBody: { required: true, content: { "application/json": { schema: { type: "object", properties: { text: { type: "string" } } } } } },
        responses: { 200: { description: "ok" } },
      },
    },
  },
};
