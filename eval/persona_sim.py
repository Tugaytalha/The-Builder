"""Talk to a phone agent through the chat route with simulated customers. No simulation slot is used.

    python eval/persona_sim.py <workflow_id> --cases kit/public-test-set.json [--style talkative+pieces] [--reps 3]
        [--only PUB-01,PUB-04] [--parallel 8] [--mode llm|script] [--lines eval/lines/regress.json] [--no-judge]

Each run opens a fresh practice session, plays the customer turn by turn on POST /api/v2/chat/message, and scores the
bank's ledger with kit/tools/score.py. The customer is the kit's persona text, played by a small Claude model. A case
passes only when all its reps pass, as in the final. This is a fast filter, not the official score.
"""
import sys
import time
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tools"))

import freya  # noqa: E402
import run_cases  # noqa: E402

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
