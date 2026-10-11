# Usage: python3 mock/test/verify_live.py <mock url> briefs/final-case/test-environment/test-customers.json
# Calls the live mock once for every answer in test-customers.json and compares status and body exactly.
import json, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
MOCK, FILE = sys.argv[1], sys.argv[2]
fx = json.load(open(FILE))
def post(name, data):
    req = urllib.request.Request(f"{MOCK}/voice/v1/{name}", json.dumps({"data": data, "call": {"ani": "5000000000", "lang": "tr"}}).encode(), {"Content-Type": "application/json", "User-Agent": "mock-check/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw)
        except ValueError: return e.code, raw[:120]
jobs = []
for c in fx["customers"]:
    n, s = c["customerNo"], c["services"]
    jobs.append(("cards.list", {"customerNo": n, "aiFlow": "CardOps"}, s["cards.list"]))
    jobs.append(("contact.email.get", {"customerNo": int(n), "intAddressInfoType": "E"}, s["contact.email.get"]))
    if "statement.pdf.send" in s:
        jobs.append(("statement.pdf.send", {"customerNo": n, "cardNumber": "x", "currencyType": "TL", "statementDate": "05.10.2026", "emailAddress": "a@b.c"}, s["statement.pdf.send"]))
    for svc in ("cards.balance", "statement.week.get"):
        for card, e in s.get(svc, {}).items(): jobs.append((svc, {"cardNumber": card}, e))
    for svc in ("statement.week.decide", "statement.week.change"):
        for card, weeks in s.get(svc, {}).items():
            for w, e in weeks.items(): jobs.append((svc, {"cardNumber": card, "newStatementWeek": int(w), "statementDay": 5}, e))
def check(job):
    name, data, e = job
    st, body = post(name, data)
    return None if (st, body) == (e["http"], e["response"]) else (name, data, st, e["http"])
bad = [r for r in ThreadPoolExecutor(4).map(check, jobs) if r]
print(f"{len(jobs) - len(bad)}/{len(jobs)} exact"); [print("DIFF", b) for b in bad[:10]]
# contract errors for unknown keys
for name, data in [("cards.list", {"customerNo": "11111111"}), ("cards.balance", {"cardNumber": "540000******0000"}), ("statement.week.get", {"cardNumber": "540000******0000"}),
                   ("statement.week.decide", {"cardNumber": "540000******1234", "newStatementWeek": 1, "statementDay": 5}), ("statement.pdf.send", {"customerNo": "11111111", "cardNumber": "x", "currencyType": "TL", "statementDate": "1", "emailAddress": "a"}),
                   ("cards.balance", {"cardNumber": ""})]:
    st, body = post(name, data); print(name, st, body["result"]["code"] if isinstance(body, dict) else body, body["result"]["message"] if isinstance(body, dict) else "")
