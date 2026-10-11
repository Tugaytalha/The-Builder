"""Summarize judge verdicts that are already in a workflow journal."""
import json, sys, pathlib
j = pathlib.Path(sys.argv[1]) / "journal.jsonl"
labels, done = {}, []
for line in j.read_text(encoding="utf-8").splitlines():
    e = json.loads(line)
    if e.get("type") == "started":
        labels[e.get("key")] = e.get("label")
    elif e.get("type") == "result" and str(labels.get(e.get("key"), "")).startswith("judge:"):
        v = e.get("result") or e.get("value") or {}
        if isinstance(v, dict) and "pass" in v:
            done.append((labels[e["key"]][6:], v))
calls = sum(1 for k, l in labels.items() if str(l).startswith("call:"))
print(f"calls started {calls}, judged {len(done)}, pass {sum(v['pass'] for _, v in done)}")
for pid, v in sorted(done):
    crit = [x for x in v["errors"] if x["severity"] == "critical"]
    major = [x for x in v["errors"] if x["severity"] == "major"]
    print(f"{pid} {'PASS' if v['pass'] else 'FAIL'} {v['score']} c{len(crit)} M{len(major)}")
    for x in crit + major:
        print("   -", x["severity"][:4], x["what"][:200].replace("\n", " "))
