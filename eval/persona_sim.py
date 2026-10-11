"""Talk to a phone agent through the chat route with simulated customers. No simulation slot is used.

    python eval/persona_sim.py <workflow_id> --cases kit/public-test-set.json [--style talkative+pieces] [--reps 3]
        [--only PUB-01,PUB-04] [--parallel 8] [--mode llm|script] [--lines eval/lines/regress.json] [--no-judge]

Each run opens a fresh practice session, plays the customer turn by turn on POST /api/v2/chat/message, and scores the
bank's ledger with kit/tools/score.py. The customer is the kit's persona text, played by a small Claude model. A case
passes only when all its reps pass, as in the final. This is a fast filter, not the official score.
"""
import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tools"))

import freya  # noqa: E402
import run_cases  # noqa: E402
import score  # noqa: E402

CUSTOMER_MODEL = "claude-haiku-5-5"
MAX_TURNS = 40
RETRY_CODES = ("-> 503", "-> 504")
ENDED = "(the call ended)"


def styled_prompt(case, style=None):
    """The kit's persona text for a case. `style` is a kit style or several joined by "+", like "talkative+pieces"."""
    base = run_cases.persona_for(case, {"identity": case["identity"]})["prompt"]
    names = [s for s in (style or case.get("style") or "").split("+") if s]
    unknown = [s for s in names if s not in run_cases.STYLES]
    if unknown:
        raise ValueError(f"unknown style {unknown}: use {sorted(run_cases.STYLES)}")
    return "\n\n".join([base] + [run_cases.STYLES[s] for s in names])


def case_passes(rows):
    """A case passes only when every rep passed (the final's rule)."""
    return bool(rows) and all(r["pass"] for r in rows)


def with_now(variables, case):
    """Session variables with the case's own `now` (spike S5: the bank accepts another day)."""
    now = (case.get("variables") or {}).get("now")
    return {**variables, "now": now} if now else dict(variables)


def chat_turn(workflow_id, variables, message, call_id=None, sleep=time.sleep):
    """One chat turn. Returns (reply, call_id). The reply is None when the call ended (the route answers 502 then)."""
    body = {"workflowId": workflow_id, "message": message, "customerVariables": variables}
    if call_id:
        body["callId"] = call_id
    for attempt in range(3):
        try:
            r = freya.api("POST", "/api/v2/chat/message", body)
            return (r.get("response") or ""), (r.get("callId") or call_id)
        except RuntimeError as exc:
            if "-> 502" in str(exc) and call_id:
                return None, call_id
            if attempt < 2 and any(c in str(exc) for c in RETRY_CODES):
                sleep(2 + attempt * 3)
                continue
            raise


def end_chat(call_id):
    try:
        freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
    except RuntimeError:
        pass


def transcript_text(turns):
    return "\n".join(f"{'AGENT' if who == 'agent' else 'CUSTOMER'}: {text}" for who, text in turns)


class ScriptCustomer:
    """Fixed lines, for regression tests with no model. The customer goes quiet when the lines run out."""

    def __init__(self, lines):
        self.lines = list(lines)

    async def reply(self, agent_text):
        return self.lines.pop(0) if self.lines else None

    async def close(self):
        pass


class LlmCustomer:
    """The kit's persona text, played by a small model. One open session per conversation."""

    def __init__(self, prompt, model=CUSTOMER_MODEL):
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
        options = ClaudeAgentOptions(model=model, system_prompt=prompt, allowed_tools=[], max_turns=1,
                                     setting_sources=[], cwd=tempfile.gettempdir())
        self.client = ClaudeSDKClient(options)
        self.started = False
        self.said_goodbye = False

    async def reply(self, agent_text):
        from claude_agent_sdk import AssistantMessage, TextBlock
        if self.said_goodbye:
            return None      # the persona says nothing after its goodbye
        if not self.started:
            await self.client.connect()
            self.started = True
        await self.client.query(agent_text or "(silence)")
        text = []
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                text += [b.text for b in message.content if isinstance(b, TextBlock)]
        said = "".join(text).strip()
        self.said_goodbye = "goodbye" in said.lower()
        return said or None

    async def close(self):
        if self.started:
            await self.client.disconnect()


async def converse(workflow_id, variables, customer, max_turns=MAX_TURNS):
    """Play one call. Returns the turns [(who, text)] and whether the agent ended the call."""
    turns, call_id, ended = [], None, False
    agent, call_id = await asyncio.to_thread(chat_turn, workflow_id, variables, "Hello?")
    turns.append(("agent", agent))
    for _ in range(max_turns):
        said = await customer.reply(agent)
        if not said:
            break
        turns.append(("customer", said))
        agent, call_id = await asyncio.to_thread(chat_turn, workflow_id, variables, said, call_id)
        if agent is None:
            turns.append(("agent", ENDED))
            ended = True
            break
        turns.append(("agent", agent))
    if call_id:
        await asyncio.to_thread(end_chat, call_id)
    return turns, ended


async def run_one(workflow_id, case, rep, style, make_customer, judge=None):
    """One call for one case: a fresh practice session, the conversation, the ledger score."""
    t0 = time.time()
    session = (await asyncio.to_thread(score.http, "/v1/practice/sessions", {"case": case["id"]}))["variables"]
    variables = with_now(session, case)
    customer = make_customer(case, style)
    try:
        turns, ended = await converse(workflow_id, variables, customer)
    finally:
        await customer.close()
    ledger = await asyncio.to_thread(score.http, "/v1/practice/ledger/" + session["customer_id"])
    failed = list(score.score_ledger(case, ledger)["failed"])
    if judge:
        failed += await judge(case, turns, ledger)
    return {"id": case["id"], "rep": rep, "pass": not failed, "failed": failed, "ended": ended, "turns": turns,
            "tools": [c["tool"] for c in ledger["calls"]], "customer_id": session["customer_id"],
            "seconds": round(time.time() - t0)}


def show(row):
    tools = " > ".join(t.replace("verify_identity", "verify").replace("create_promise", "promise") for t in row["tools"])
    print(("PASS" if row["pass"] else "FAIL"), row["id"], f"rep {row['rep'] + 1}", f"{row['seconds']:>3}s", "|",
          tools or "(no tool calls)", flush=True)
    for f in row["failed"]:
        print("       -", f[:260], flush=True)


async def run_all(workflow_id, cases, reps, style, make_customer, parallel, judge=None):
    gate = asyncio.Semaphore(parallel)
    rows = {c["id"]: [] for c in cases}

    async def job(case, rep):
        async with gate:
            try:
                row = await run_one(workflow_id, case, rep, style, make_customer, judge)
            except Exception as exc:     # one broken call must not stop the rest
                row = {"id": case["id"], "rep": rep, "pass": False, "failed": ["harness error: " + repr(exc)[:300]],
                       "ended": False, "turns": [], "tools": [], "customer_id": "", "seconds": 0}
        show(row)
        rows[case["id"]].append(row)

    await asyncio.gather(*(job(c, r) for c in cases for r in range(reps)))
    return rows


def write_results(rows, out, meta):
    out = Path(out)
    (out / "failures").mkdir(parents=True, exist_ok=True)
    summary = {**meta, "cases": {}}
    for cid, runs in sorted(rows.items()):
        runs.sort(key=lambda r: r["rep"])
        summary["cases"][cid] = {"pass": case_passes(runs), "reps": [
            {k: r[k] for k in ("pass", "failed", "tools", "seconds", "ended")} for r in runs]}
        for r in runs:
            if not r["pass"]:
                (out / "failures" / f"{cid}-rep{r['rep'] + 1}.txt").write_text(
                    "\n".join(r["failed"]) + "\n\n" + transcript_text(r["turns"]) + "\n", encoding="utf-8")
    summary["passed"] = sum(1 for c in summary["cases"].values() if c["pass"])
    summary["total"] = len(summary["cases"])
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow_id")
    ap.add_argument("--cases", default=str(KIT / "public-test-set.json"))
    ap.add_argument("--style", default=None, help="a kit style, or several joined by +")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--parallel", type=int, default=8, help="at most 8: do not load-test the platform")
    ap.add_argument("--mode", choices=("llm", "script"), default="llm")
    ap.add_argument("--lines", help="script mode: a JSON file {case id: [customer lines]}")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", help="result folder, default eval/results/sim/<time>")
    a = ap.parse_args(argv)
    if a.parallel > 8:
        ap.error("--parallel above 8 is not allowed")
    cases = json.load(open(a.cases, encoding="utf-8"))
    if a.only:
        wanted = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    if a.mode == "script":
        if not a.lines:
            ap.error("--mode script needs --lines")
        scripts = json.load(open(a.lines, encoding="utf-8"))
        cases = [c for c in cases if c["id"] in scripts]
        make = lambda case, style: ScriptCustomer(scripts[case["id"]])
    else:
        make = lambda case, style: LlmCustomer(styled_prompt(case, style))
    if not cases:
        sys.exit("no cases to run")
    for c in cases:
        styled_prompt(c, a.style)       # fail early on an unknown style
    out = a.out or str(Path(__file__).resolve().parent / "results" / "sim" / time.strftime("%Y%m%d-%H%M%S"))
    t0 = time.time()
    rows = asyncio.run(run_all(a.workflow_id, cases, a.reps, a.style, make, a.parallel))
    summary = write_results(rows, out, {"workflow_id": a.workflow_id, "style": a.style, "reps": a.reps, "mode": a.mode,
                                        "customer_model": CUSTOMER_MODEL if a.mode == "llm" else None})
    print(f"\n{summary['passed']} / {summary['total']} cases passed ({a.reps} rep{'s' if a.reps > 1 else ''}, "
          f"all must pass), {round(time.time() - t0)} s. Results: {out}")


if __name__ == "__main__":
    main()
