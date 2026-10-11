import json, sys, pathlib
R = pathlib.Path(__file__).parent / "runs"
mode, *ids = sys.argv[1:]
for p in ids:
    d = json.loads((R / f"{p}.json").read_text(encoding="utf-8"))
    if mode == "turns":
        print(p, json.dumps(d["turns"], ensure_ascii=False)[:600])
    elif mode == "around":
        ev = d.get("events", []); key = sys.argv[2] if False else None
        idx = [k for k, e in enumerate(ev) if "week.change" in e or "pdf.send" in e]
        for k in idx: print("\n".join(ev[k:k + 8])); print("----")
    elif mode == "events":
        print("\n".join(e[:400] for e in d.get("events", [])))
