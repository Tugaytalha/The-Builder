// The tool API the phone agent gets: one operation per service, with the contract's request envelope
// ({"data": {...}, "call": {...}}) and field names. The Worker adds `servers` with its own address.
import { SERVICES } from "./services.js";
import { BASE } from "./routes.js";

const CALL = { type: "object", description: "Call metadata the bank logs. Not checked.", properties: { ani: { type: "string" }, lang: { type: "string", enum: ["tr"] } } };
const RESULT = { type: "object", description: "result.returnCode \"1\" is success; anything else is an error and the answer has no data.", properties: { returnCode: { type: "string" }, code: { type: "string" }, message: { type: "string" }, type: { type: "string" } } };

export const OPENAPI = {
  openapi: "3.0.0",
  info: { title: "Freya Bank voice assistant: statement and debt services", version: "2026-10-01" },
  paths: Object.fromEntries(
    Object.entries(SERVICES).map(([name, spec]) => [
      BASE + name,
      {
        post: {
          operationId: name,
          summary: spec.summary,
          requestBody: {
            required: true,
            content: { "application/json": { schema: { type: "object", required: ["data"], properties: { data: { type: "object", required: spec.required, properties: spec.fields }, call: CALL } } } },
          },
          responses: { 200: { description: "Success", content: { "application/json": { schema: { type: "object", properties: { data: { type: "object" }, result: RESULT } } } } } },
        },
      },
    ]),
  ),
};
