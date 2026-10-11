"""Print a simulated call compactly: what each side said, tool calls with their arguments and results, node changes.

    python reference-agent/show_call.py <call_id> [<call_id> ...]
    python reference-agent/show_call.py --results reference-agent/results/a-run1.json [--failed]
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "kit"))
import freya


def show(call_id):
    call = freya.get_call(call_id)
    print(f"=== call {call_id}  ended: {call.get('endedReason')}  {call.get('duration')} s")
    for m in call.get("messages", []):
        role, text = m.get("role"), m.get("message") or ""
        if role in ("assistant", "user"):
            print(f"  {'AGENT' if role == 'assistant' else 'USER '} [{m.get('nodeId') or ''}] {text}")
            continue
        try:
            ev = json.loads(text)
        except Exception:
            continue
        e = ev.get("event")
        if e == "node_enter":
            print(f"  -> node {ev.get('node')}")
        elif e == "function_call_start":
            body = (ev.get("args") or {}).get("body", ev.get("args"))
            url = str((ev.get("args") or {}).get("url", ""))
            print(f"  TOOL {ev.get('function')}({json.dumps(body)})" + ("  [REDIRECTED]" if url and not url.endswith(str(ev.get('function'))) else ""))
        elif e == "function_call_complete":
            r = ev.get("result")
            d = r.get("data") if isinstance(r, dict) else r
            print(f"       = {json.dumps(d)[:400]}")
        elif e in ("function_call_error", "error"):
            print(f"       ! {e}: {str(ev.get('error') or ev.get('message'))[:300]}")
        elif e == "variable_extracted":
            print(f"       ~ {ev.get('name')} = {ev.get('value')}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--results":
        res = json.load(open(args[1]))
        for row in res["rows"]:
            if "--failed" in args and row["pass"]:
                continue
            print(f"\n##### {row['id']} {'PASS' if row['pass'] else 'FAIL'}: {row['failed']}")
            if row.get("call_id"):
                show(row["call_id"])
    else:
        for c in args:
            show(c)
