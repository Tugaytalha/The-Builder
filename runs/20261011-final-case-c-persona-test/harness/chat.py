"""Talk to the final-case agent turn by turn and keep a transcript.

  python chat.py start <run_name> <customerNumber> <now> "<first message>"
  python chat.py say   <run_name> "<message>"
  python chat.py end   <run_name>
  python chat.py show  <run_name>

State and transcript: runs/<run_name>.json next to this script.
"""
import json, os, sys, time, pathlib
sys.path.insert(0, os.environ["KIT_DIR"])
import freya

WORKFLOW_ID = os.environ.get("WF_ID", "316f8730-9dc4-4858-bc8d-adf1a9537e40")
DIR = pathlib.Path(__file__).parent / "runs"; DIR.mkdir(exist_ok=True)

def load(name): return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))
def save(name, s): (DIR / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")

def turn(s, msg):
    body = {"workflowId": WORKFLOW_ID, "message": msg, "customerVariables": s["vars"]}
    if s.get("callId"): body["callId"] = s["callId"]
    for i in range(4):
        try:
            r = freya.api("POST", "/api/v2/chat/message", body)
            s["callId"] = r.get("callId") or s.get("callId")
            return r.get("response") or ""
        except RuntimeError as e:
            if " 502" in str(e) and s.get("callId"):
                s["ended"] = True; return "[CALL ENDED BY AGENT]"
            if i == 3: return f"[ERROR {str(e)[:300]}]"
            time.sleep(3 * (i + 1))

def compact(messages):
    """Spoken lines, nodes entered, service calls with their answers, tool choices. No code bodies."""
    out = []
    for m in messages:
        role, msg = m.get("role"), m.get("message", "")
        if role in ("user", "assistant", "bot"):
            out.append(f"{role.upper()}: {msg}"); continue
        try: j = json.loads(msg)
        except Exception: continue
        ev = j.get("event")
        if ev == "node_enter": out.append(f"  [node] {j.get('node')}")
        elif ev == "function_call_start" and j.get("function") == "api_call":
            a = j.get("args", {}); out.append(f"  [api] {a.get('url', '').rsplit('/', 1)[-1]} {json.dumps(a.get('body'), ensure_ascii=False)}")
        elif ev == "function_call_start" and j.get("function") != "code_exec":
            out.append(f"  [tool] {j.get('function')} {json.dumps((j.get('args') or {}).get('params'), ensure_ascii=False)}")
        elif ev == "function_call_complete" and j.get("function") == "api_call":
            out.append(f"  [api-result] {json.dumps(j.get('result'), ensure_ascii=False)[:1500]}")
        elif ev == "function_call_complete" and j.get("function") == "code_exec" and (j.get("result") or {}).get("status") != "success":
            out.append(f"  [code-error] {json.dumps(j.get('result'), ensure_ascii=False)[:500]}")
    return out

def main():
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "start":
        s = {"vars": {"customerNumber": sys.argv[3], "now": sys.argv[4]}, "turns": [], "ended": False}
        msg = sys.argv[5]
    elif cmd in ("say",):
        s = load(name); msg = sys.argv[3]
        if s.get("ended"): print("AGENT: [CALL ALREADY ENDED]"); return
    elif cmd == "end":
        s = load(name)
        if s.get("callId") and not s.get("ended"):
            try: freya.api("POST", "/api/v2/chat/end", {"callId": s["callId"]})
            except RuntimeError: pass
        s["ended"] = True
        try:
            s["events"] = compact(freya.get_call(s["callId"]).get("messages", []))
        except Exception as e: s["events_error"] = str(e)[:300]
        save(name, s); print("ENDED"); return
    elif cmd == "show":
        print(json.dumps(load(name), ensure_ascii=False, indent=1)); return
    s["turns"].append({"customer": msg})
    resp = turn(s, msg)
    s["turns"][-1]["agent"] = resp
    save(name, s)
    print("AGENT:", resp)
    if s.get("ended"): print("[CALL ENDED]")

main()
