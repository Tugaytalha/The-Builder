// The mock of the bank's services for the final case. One Durable Object holds the whole state, so a write is seen
// by the next read. Routes and data come from the case's service contract and test customers (src/routes.js,
// src/data.js, src/openapi.js). /openapi.json is what builder/build.py reads; /__log and /__reset are ours only.
import { DurableObject } from "cloudflare:workers";
import { OPENAPI } from "./openapi.js";
import { ROUTES } from "./routes.js";
import { seed } from "./data.js";
import { match } from "./match.js";

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8" } });

export class Bank extends DurableObject {
  async handle(method, path, body) {
    const state = (await this.ctx.storage.get("state")) ?? seed();
    const log = (await this.ctx.storage.get("log")) ?? [];
    if (path === "/__log") return { status: 200, data: log };
    if (path === "/__reset") {
      await this.ctx.storage.put({ state: seed(), log: [] });
      return { status: 200, data: { ok: true } };
    }
    const found = match(ROUTES, method, path);
    let status = 404, data = { ok: false, error: "unknown route" };
    if (found) {
      try {
        ({ status = 200, data } = found.route(state, { ...(body ?? {}), ...found.params }));
      } catch (err) {
        status = 500;
        data = { ok: false, error: String(err) };
      }
    }
    log.push({ at: new Date().toISOString(), method, path, body, status, data });
    await this.ctx.storage.put({ state, log: log.slice(-2000) });
    return { status, data };
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/openapi.json") return json({ ...OPENAPI, servers: [{ url: url.origin }] });
    if (url.pathname === "/health") return json({ ok: true });
    let body = null;
    if (request.method !== "GET") body = await request.json().catch(() => null);
    else if (url.search) body = Object.fromEntries(url.searchParams);
    const bank = env.BANK.get(env.BANK.idFromName("bank"));
    const { status, data } = await bank.handle(request.method, url.pathname, body);
    return json(data, status);
  },
};
