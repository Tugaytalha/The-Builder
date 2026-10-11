"""Run the negotiation code of an exported phone agent locally, on multi-product sequences, with no platform call.

    .venv/Scripts/python eval/repro_multi_product.py brief-ab      # or v3-raw-b

It loads submission/<slot>.workflow.json, runs its `setup` and `prepare` nodes and its `customer_said` tool with
invented products, and prints the state after each customer message. Each scenario is one defect class from
notes/multi-product-review.md. Read the printed state; the script asserts nothing. The products are invented,
not a practice customer.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from builder.blocks.coderun import node_code, run_snippet, run_tool, tool_code  # noqa: E402

slot = sys.argv[1] if len(sys.argv) > 1 else "brief-ab"
W = json.load(open(os.path.join(ROOT, "submission", slot + ".workflow.json"), encoding="utf-8"))["workflow"]
PRODS = [dict(product_id="P1", type="credit_card", past_due=300, days_late=10, minimum_payment=50, card_last4="4821"),
         dict(product_id="P2", type="personal_loan", past_due=200, days_late=3, instalment_amount=80),
         dict(product_id="P3", type="car_loan", past_due=500, days_late=20, instalment_amount=150)]


def base(n=2, now="2026-10-14T11:00"):
    v = run_snippet(node_code(W, "setup"), {"now": now, "customer_id": "C1"})
    v["products"] = json.dumps(PRODS[:n])
    return run_snippet(node_code(W, "prepare"), v)


def said(v, answers, reply=""):
    v = dict(v)
    v.pop("say_turn", None)
    entries = [{"kind": "", "date": "", "amount": "", "item": "", **a} for a in answers]
    return run_tool(tool_code(W, "customer_said"), v, {"answers": entries, "reply": reply})


def show(tag, v):
    st = json.loads(v["neg_state"])
    print("  %-30s guide=%s | close=%s action=%s record=%s error=%s" % (
        tag, v.get("guide"), v.get("close_key"), v.get("negotiation_action"), v.get("record_now"),
        v.get("customer_said_code_error")))
    print("    items:", [(x["id"], x["status"], x.get("used"), x.get("agreed"), x.get("note"), x.get("asked"))
                         for x in st["items"]])


def scenario(title):
    print("=== " + title)
    return base()


v = scenario("1. A change at the final read-back for P2 (expected: only P2 changes)")
v = said(v, [dict(kind="proposes", item="P1", date="2026-10-16", amount="300"),
             dict(kind="proposes", item="P2", date="2026-10-19", amount="200")]); show("both propose", v)
v = said(v, [dict(kind="proposes", item="P2", date="2026-10-20")]); show("P2 to 20 Oct at read-back", v)

v = scenario("2. P1 paid, P2 agreed, then a change for P2 at the read-back (expected: P1 stays paid)")
v = said(v, [dict(kind="paid", item="P1"), dict(kind="proposes", item="P2", date="2026-10-19", amount="200")]); show("t1", v)
v = said(v, [dict(kind="proposes", item="P2", date="2026-10-20")]); show("P2 to 20 Oct at read-back", v)

v = scenario("3. 'Yes' at the read-back sent as accepts (expected: same as confirms, plan unchanged)")
v = said(v, [dict(kind="refuses", item="P1")]); show("P1 no", v)
v = said(v, [dict(kind="proposes", item="P1", amount="250", date="2026-10-19")]); show("P1 counter", v)
v = said(v, [dict(kind="proposes", item="P2", amount="200", date="2026-10-19")]); show("P2 agreed", v)
v = said(v, [dict(kind="accepts")]); show("yes as accepts", v)

v = scenario("4. A stored line is said, then a question on that product (expected: no extra attempt)")
v = said(v, [dict(kind="refuses", item="P1"), dict(kind="refuses", item="P2")]); show("both no", v)
v = said(v, [dict(kind="proposes", item="P1", date="2026-10-16", amount="300")]); show("P1 agreed", v)
v = said(v, [dict(kind="other", item="P2")], reply="It is your personal loan."); show("question on P2", v)

v = scenario("5. A product named by type, not by id (expected: P2 noted paid, P1 still open)")
v = said(v, [dict(kind="paid", item="personal_loan")]); show("loan paid, item=personal_loan", v)

v = scenario("6. 'Yes, all of them today' as one entry (expected: every product agreed for today)")
v = said(v, [dict(kind="accepts")]); show("yes all today", v)

v = scenario("7. One date for all, after P1's deadline, sent as one proposes per product")
v = said(v, [dict(kind="proposes", item="P1", date="2026-10-30"), dict(kind="proposes", item="P2", date="2026-10-30")]); show("t1", v)
v = said(v, [dict(kind="accepts", item="P1")]); show("yes", v)

print("=== 8. Three products, refusals to the end (expected: three refused notes, close no_promise/refused)")
v = base(3)
for i in range(7):
    v = said(v, [dict(kind="refuses")]); show("refusal %d" % (i + 1), v)
    if v.get("close_key"):
        break
