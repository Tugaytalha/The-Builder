import json, sys
sys.path.insert(0, "kit")
import freya
for cid in sys.argv[1:]:
    c = freya.get_call(cid)
    print("=====", cid)
    for m in c["messages"]:
        role = m.get("role"); txt = str(m.get("content") or m.get("message") or "")
        if role in ("user", "assistant"): print(f"  [{role}] {txt[:300]}")
        elif '"function_call_start"' in txt:
            e = json.loads(txt); a = e.get("args", {})
            if e["function"] == "code_exec": continue
            print(f"     -> {e['function']} {json.dumps(a.get('params') or a.get('body') or '')[:250]}")
        elif '"route_evaluated"' in txt and '"matched":true' in txt:
            e = json.loads(txt)
            if "always" not in e.get('reason',''): print(f"     ~ {e['from_node']} -> {e['target']} ({e.get('reason','')[:80]})")
