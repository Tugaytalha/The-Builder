from run_cases_at import wrap
from run_eval import classify, report


def test_now_override():
    fake = lambda path, body=None: {"variables": {"now": "2026-10-14T11:00", "customer_id": "c1"}}
    out = wrap(fake, {"PUB-01": "2026-10-19T11:00"})("/v1/practice/sessions", {"case": "PUB-01"})
    assert out["variables"] == {"now": "2026-10-19T11:00", "customer_id": "c1"}


def test_other_routes_are_unchanged():
    fake = lambda path, body=None: {"variables": {"now": "x"}}
    assert wrap(fake, {"PUB-01": "y"})("/v1/practice/ledger/c1")["variables"]["now"] == "x"


def test_classify():
    # reason strings from runs/20261010-step6-7/*.json
    assert classify("outcome ('not_verified', 'declined'), expected ('promise', None)") == "identity"
    assert classify("conversation: The support team was offered three times instead of the required 'once'") == "attempts"
    assert classify("conversation: the loan deadline was missed") == "dates"
    assert classify("promises [('p1', 640.0, '2026-10-16')], expected [('p1', 637.5, '2026-10-16')]") == "amounts"
    assert classify("conversation: The agent said 'recorded' in message 0") == "wording"
    assert classify("notes [], expected [('p2', 'refused'), ('p3', 'refused')]") == "closing"
    assert classify("conversation: no verdict") == "platform"
    assert classify("something new") == "other"


def test_report_shows_change():
    old = {"rows": [{"name": "brief-a", "set": "dev", "passed": 7, "total": 10}]}
    new = [{"name": "brief-a", "set": "dev", "passed": 9, "total": 10, "build_s": 900, "build_exit": 0,
            "failures": [{"id": "PUB-03", "reasons": ["outcome ('not_verified', 'failed'), expected ('promise', None)"]}]}]
    text = report(new, old)
    assert "| brief-a | dev | 9 | 10 | 900 | 0 | +2 |" in text and "## identity (1)" in text
