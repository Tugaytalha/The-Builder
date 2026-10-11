import json, sys, time
sys.path.insert(0, "kit/tools")
from score import http
from builder.blocks.check import freya
wid = sys.argv[1]
v = http("/v1/practice/sessions", {"case": sys.argv[2]})["variables"]
lines = json.load(open(sys.argv[3]))
cid = None
for line in lines:
    b = {"workflowId": wid, "message": line, "customerVariables": v}
    if cid: b["callId"] = cid
    try:
        r = freya.api("POST", "/api/v2/chat/message", b); cid = r.get("callId") or cid
        print("U:", line, "\nA:", r.get("response"))
    except RuntimeError as e:
        print("ended", str(e)[:50]); break
time.sleep(4)
led = http("/v1/practice/ledger/" + v["customer_id"])
print("BANK promises", [(p["product_id"], p["amount"], p["date"]) for p in led["promises"]], "notes", [(n.get("product_id"), n["reason"]) for n in led["notes"]], "callbacks", led.get("callbacks"), "outcome", led["outcome"], led["reason"])
print("CALL ID", cid)
for m in freya.get_call(cid)["messages"]:
    if m["role"] == "system":
        e = json.loads(m["message"])
        if e.get("event") == "function_call_start" and e["function"] == "customer_said": print("  CALL", json.dumps(e["args"].get("params")))
        if e.get("event") == "route_evaluated" and e.get("from_node") == "negotiate":
            vt = e.get("variable_table", {}); print("  guide=", vt.get("guide")); print("  state=", str(vt.get("neg_state"))[:600])
    elif m["role"] in ("user", "assistant"): print(m["role"][0].upper(), m["message"][:120])
