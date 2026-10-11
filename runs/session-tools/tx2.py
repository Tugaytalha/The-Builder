import json, sys
sys.path.insert(0, "kit")
import freya
d = json.load(open(sys.argv[1]))
for r in d["rows"]:
    if r["id"] not in sys.argv[2:]: continue
    c = freya.get_call(r["call_id"])
    print("=====", r["id"], r["call_id"])
    for m in c["messages"]:
        role = m.get("role"); txt = str(m.get("content") or m.get("message") or m.get("text") or "")
        if role in ("user", "assistant"): print(f"  [{role}] {txt[:300]}")
        elif '"function_call_start"' in txt:
            e = json.loads(txt); a = e.get("args", {})
            if e["function"] in ("code_exec",): continue
            print(f"     -> {e['function']} {json.dumps(a.get('params') or a.get('body') or '')[:200]}")
        elif '"route_evaluated"' in txt and '"matched":true' in txt:
            e = json.loads(txt); print(f"     ~ {e['from_node']} -> {e['target']} ({e.get('reason','')[:80]})")
