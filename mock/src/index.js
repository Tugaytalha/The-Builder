// The mock of the bank's services for the final case (src/routes.js). The answers are fixed by the test customers file,
// so the Durable Object only keeps the request log. /openapi.json is what builder/build.py reads; /__log and /__reset
// are ours only. /oauth2/token answers like the bank's gateway; the test environment does not check the token.
import { DurableObject } from "cloudflare:workers";
import { OPENAPI } from "./openapi.js";
import { ROUTES } from "./routes.js";

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8" } });

export class Bank extends DurableObject {
  async log(entry) {
    const log = (await this.ctx.storage.get("log")) ?? [];
    log.push(entry);
    await this.ctx.storage.put("log", log.slice(-2000));
  }
  async read() {
    return (await this.ctx.storage.get("log")) ?? [];
  }
  async reset() {
    await this.ctx.storage.delete("log");
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const bank = env.BANK.get(env.BANK.idFromName("bank"));
    if (url.pathname === "/openapi.json") return json({ ...OPENAPI, servers: [{ url: url.origin }] });
    if (url.pathname === "/health") return json({ ok: true });
    if (url.pathname === "/__log") return json(await bank.read());
    if (url.pathname === "/__reset") return json((await bank.reset(), { ok: true }));
    if (url.pathname === "/oauth2/token") return json({ access_token: "test-token", token_type: "Bearer", expires_in: 1800 });
    const route = ROUTES[`${request.method} ${url.pathname}`];
    const body = await request.json().catch(() => null);
    // The contract's envelope puts the fields in `data`; a flat body is read the same way.
    const data = body && typeof body.data === "object" && body.data !== null ? body.data : (body ?? {});
    const { status, data: out, delay } = route ? route(data) : { status: 404, data: { ok: false, error: "unknown route" }, delay: 0 };
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay * 1000));
    await bank.log({ at: new Date().toISOString(), method: request.method, path: url.pathname, body, status, data: out });
    return json(out, status);
  },
};
