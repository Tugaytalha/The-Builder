"""Run the sandbox snippets locally the way Freya runs them (globals vars / config / result) on the practice cases.

    python reference-agent/test_sandbox.py

Checks, per case, that the facts the agent gets agree with the expected bank records, that the expected promises
pass the promise guard, that wrong promises are blocked, and that close_call ends up with the expected outcome.
"""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build

CASES = json.loads((build.KIT / "public-test-set.json").read_text(encoding="utf-8"))
fails = 0


def run(code, vars, **extra):
    g = {"vars": vars, **extra}
    exec(compile(code, "<snippet>", "exec"), g)
    return g


def check(ok, msg):
    global fails
    if not ok:
        fails += 1
        print("   FAIL", msg)


def ok_result(**data):
    return {"status": "success", "status_code": 200, "data": {"ok": True, **data}, "header": {"x": "y"}}


def fresh(v, **kw):
    """A copy of the call state without any recorded promise or note."""
    out = {k: x for k, x in v.items() if not (k.startswith("st_prom_") or k.startswith("st_note_"))}
    out.update(st_promises="[]", st_notes="[]")
    out.update(kw)
    return out


for case in CASES:
    multi = case["brief"] == "B"
    h = {k: build.snippet(v, multi) for k, v in build.hooks().items()}
    v = {"customer_id": "c_x", "now": case["variables"]["now"], **case["variables"]}
    run(build.snippet((HERE / "sandbox" / "setup.py").read_text(encoding="utf-8"), multi), v)
    products = [{"product_id": f"p{i + 1}", **p} for i, p in enumerate(case["products"])]
    res = ok_result(products=products)
    run(h["account_post"], v, result=res)
    run(build.snippet((HERE / "sandbox" / "account.py").read_text(encoding="utf-8"), multi), v)
    print(case["id"], case["title"], "|", v.get("account_state"), "|", v["debt_statement"][:110])
    check(v.get("account_state") == "known", "account facts not computed: " + str(v.get("account_error")))
    meta = json.loads(v["st_meta"])
    exp = case["expected"]

    # every expected promise passes the guard and is recorded once
    v["st_verified"] = "yes"
    for p in exp["promises"]:
        cfg = {"url": "https://bank.example/v1/create_promise", "body": {"customer_id": "c_x", "product_id": p["product_id"], "amount": str(p["amount"]), "date": p["date"]}}
        run(h["promise_pre"], v, config=cfg)
        check(v["st_block_promise"] == "", f"expected promise {p} blocked: {v['st_block_promise']}")
        check(cfg["url"].endswith("/create_promise"), "a valid promise was redirected")
        r = ok_result(promise_id="x")
        run(h["promise_post"], v, result=r)
        check("recorded" in r["data"]["what_to_do_next"].lower() or "Recorded" in r["data"]["what_to_do_next"], "post-hook message: " + r["data"]["what_to_do_next"])
    for n in exp["notes"]:
        cfg = {"body": {"customer_id": "c_x", "product_id": n["product_id"], "reason": n["reason"]}}
        run(h["note_pre"], v, config=cfg)
        check(v["st_block_note"] == "", f"expected note {n} blocked: {v['st_block_note']}")
        run(h["note_post"], v, result=ok_result())
    for c in exp["callbacks"]:
        cfg = {"body": {"customer_id": "c_x", "date": c["date"], "time": c["time"]}}
        run(h["callback_pre"], v, config=cfg)
        run(h["callback_post"], v, result=ok_result())
    for t in exp["transfers"]:
        cfg = {"body": {"customer_id": "c_x", "queue": t["queue"]}}
        run(h["transfer_pre"], v, config=cfg)
        run(h["transfer_post"], v, result=ok_result())

    # a wrong promise is blocked: a day after the latest deadline, and an amount under the floor
    m0 = meta[0]
    late = build.SPEC["HOLIDAYS"][-1]
    url = "https://bank.example/v1/create_promise"
    cfg = {"url": url, "body": {"customer_id": "c_x", "product_id": m0["product_id"], "amount": m0["past_due"], "date": late}}
    v2 = fresh(v)
    run(h["promise_pre"], v2, config=cfg)
    check(v2["st_block_promise"] and cfg["url"].endswith("/get_account"), "promise after the deadline was not blocked")
    r = ok_result(products=[])
    run(h["promise_post"], v2, result=r)
    check(r["data"]["ok"] is False and "NOT recorded" in r["data"]["what_to_do_next"], "blocked promise not reported: " + str(r["data"]))
    cfg = {"url": url, "body": {"customer_id": "c_x", "product_id": m0["product_id"], "amount": m0["floor"] - 1, "date": v["now"][:10]}}
    run(h["promise_pre"], v2, config=cfg)
    check(v2["st_block_promise"] and cfg["url"].endswith("/get_account"), "promise under the floor was not blocked")

    if case["id"] == "PUB-10":
        v3 = fresh(v, create_promise_failure_count=2)
        cfg = {"body": {"customer_id": "c_x", "outcome": "no_promise", "reason": "refused"}}
        run(h["close_pre"], v3, config=cfg)
        check((cfg["body"]["outcome"], cfg["body"].get("reason")) == ("no_promise", "service_error"), "two failures did not close as service_error")

    if case["id"] == "PUB-09":
        v4 = dict(v, st_transfer="", st_verified="yes", st_close_blocks="0")
        cfg = {"url": "https://bank.example/v1/close_call", "body": {"customer_id": "c_x", "outcome": "transferred", "reason": "restructuring"}}
        run(h["close_pre"], v4, config=cfg)
        check(cfg["url"].endswith("/get_account") and v4["st_block_close"], "close before a confirmed transfer was not held back")
        r = ok_result(products=[])
        run(h["close_post"], v4, result=r)
        check("NOT closed" in r["data"]["what_to_do_next"], "held-back close not reported")
    if case["id"] == "PUB-12":
        v5 = fresh(v, st_promises=json.dumps([{"product_id": "p1"}]), st_notes=json.dumps([{"product_id": "p2", "reason": "refused"}]), st_close_blocks="0")
        cfg = {"url": "https://bank.example/v1/close_call", "body": {"customer_id": "c_x", "outcome": "promise"}}
        run(h["close_pre"], v5, config=cfg)
        check(cfg["url"].endswith("/get_account") and "car loan" in v5["st_block_close"], "close with a product missing its note was not held back")

    if case["id"] == "PUB-12":
        # parallel add_note calls: each post-hook starts from the same snapshot; the last full write must not lose a note
        base = dict(v, st_close_blocks="0")
        for k in [k for k in list(base) if k.startswith("st_note_") or k == "st_notes"]:
            base.pop(k)
        snap_a, snap_b = dict(base), dict(base)
        run(h["note_pre"], snap_a, config={"body": {"customer_id": "c_x", "product_id": "p2", "reason": "refused"}})
        run(h["note_pre"], snap_b, config={"body": {"customer_id": "c_x", "product_id": "p3", "reason": "refused"}})
        run(h["note_post"], snap_a, result=ok_result())
        run(h["note_post"], snap_b, result=ok_result())
        merged = dict(base)
        merged.update({k: x for k, x in snap_a.items() if k.startswith("st_note_")})
        merged.update({k: x for k, x in snap_b.items() if k.startswith("st_note_")})
        cfg = {"url": "https://bank.example/v1/close_call", "body": {"customer_id": "c_x", "outcome": "promise"}}
        run(h["close_pre"], merged, config=cfg)
        check(cfg["url"].endswith("/close_call"), "close held back after parallel notes: " + str(merged.get("st_block_close")))

    # close_call: the model's guess is corrected from the records where the records can tell
    guess = {"transferred": "transferred", "promise": "no_promise", "paid": "paid"}.get(exp["outcome"], exp["outcome"])
    if case["id"] == "PUB-03":
        v["st_verified"] = "no"; v["st_verify_failed"] = "yes"; guess = "no_promise"
    if exp["outcome"] == "not_reached":
        v["st_verified"] = "no"
    cfg = {"body": {"customer_id": "c_x", "outcome": guess, "reason": exp.get("reason") or "refused"}}
    run(h["close_pre"], v, config=cfg)
    got = (cfg["body"]["outcome"], cfg["body"].get("reason"))
    check(got == (exp["outcome"], exp.get("reason")), f"close_call {got}, expected {(exp['outcome'], exp.get('reason'))}")

print("\nproducts_text of PUB-13:\n" + v["products_text"] if case["id"] == "PUB-13" else "")
print("\ncalendar of PUB-13 (first 16 lines):\n" + "\n".join(v["calendar_text"].splitlines()[:16]))
print("\n" + ("ALL CHECKS PASSED" if not fails else f"{fails} CHECKS FAILED"))
sys.exit(1 if fails else 0)
