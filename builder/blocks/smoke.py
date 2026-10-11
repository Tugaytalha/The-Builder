"""Short scripted chats through /api/v2/chat/message.

    python -m builder.blocks.smoke <workflow_id> <script.json>

Script: {"variables": {...}, "opening": {"absent": [...], "any": [...]},
         "turns": [{"say": "...", "absent": [...], "any": [...]}]}
"""
import json
import re
import sys

from builder.blocks.check import freya

ENDED = "(the call ended)"


def chat(workflow_id, variables, lines):
    """Send "Hello?" and then each line. Returns one reply per message sent."""
    replies, call_id = [], None
    for line in ["Hello?"] + list(lines):
        body = {"workflowId": workflow_id, "message": line, "customerVariables": variables}
        if call_id:
            body["callId"] = call_id
        try:
            r = freya.api("POST", "/api/v2/chat/message", body)
        except RuntimeError as exc:
            if not any(code in str(exc) for code in ("-> 502", "-> 504")) or not call_id:
                raise
            replies.append(ENDED)  # the chat route answers 502 or 504 on the turn that ends the call
            return replies         # no /chat/end: it runs the end-of-call tools again (close_call twice, rehearsal)
        call_id = r.get("callId") or call_id
        replies.append(r.get("response") or "")
    try:
        freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
    except RuntimeError:
        pass
    return replies


def _turn_problems(label, reply, rule):
    problems = []
    for word in rule.get("absent", []):
        if re.search(r"\b" + re.escape(word) + r"\b", reply, re.IGNORECASE):
            problems.append(f"{label}: says {word!r}: {reply}")
    wanted = rule.get("any", [])
    if wanted and not any(w.lower() in reply.lower() for w in wanted):
        problems.append(f"{label}: says none of {wanted}: {reply}")
    return problems


def run_script(workflow_id, script):
    turns = script.get("turns", [])
    replies = chat(workflow_id, script.get("variables", {}), [t["say"] for t in turns])
    problems = _turn_problems("opening", replies[0], script.get("opening", {}))
    for i, turn in enumerate(turns):
        reply = replies[i + 1] if i + 1 < len(replies) else ENDED
        problems += _turn_problems(f"turn {i + 1} ({turn['say']!r})", reply, turn)
    for i, reply in enumerate(replies):
        print(f"agent {i}: {reply}")
    return problems


if __name__ == "__main__":
    found = run_script(sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8")))
    for p in found:
        print("PROBLEM " + p)
    print("smoke: " + ("OK" if not found else f"{len(found)} problems"))
    sys.exit(1 if found else 0)
