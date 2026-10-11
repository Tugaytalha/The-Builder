"""Rebuild persona files (with expectations) and per-customer data in the scratchpad for a re-run."""
import json, re, pathlib
REPO = pathlib.Path(r"C:\Users\Tugay Talha İçen\Desktop\GitHub\The-Builder")
S = pathlib.Path(__file__).parent
RUN = REPO / "runs" / "20261011-final-persona-test"
md = (REPO / "notes" / "final-case-persona-test-calls.md").read_text(encoding="utf-8")
expect = {m.group(1): m.group(2).strip() for m in re.finditer(r"^## (p\d+)\n(?:.*\n)*?- \*\*Expected:\*\* (.*)$", md, re.M)}
(S / "personas").mkdir(exist_ok=True)
for p in json.loads((RUN / "personas.json").read_text(encoding="utf-8")):
    p["expect"] = expect.get(p["id"], "")
    (S / "personas" / f"{p['id']}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
(S / "customers").mkdir(exist_ok=True)
data = json.loads((REPO / "briefs" / "final-case" / "test-environment" / "test-customers.json").read_text(encoding="utf-8"))
for c in data["customers"]:
    (S / "customers" / f"{c['customerNo']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(expect), "expectations,", len(data["customers"]), "customers")
