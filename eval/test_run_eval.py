from run_cases_at import wrap
from run_eval import classify, report, slot_of


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


def test_unstick_completes_a_simulation_whose_runs_ended():
    from run_cases_at import STUCK_S, unstick
    calls, clock = [], [0]

    def api(method, path, body=None, **params):
        calls.append((method, path))
        if path.endswith("/iterations"):
            return {"iterations": [{"id": "it1"}]}
        if "/iterations/" in path:
            return {"runs": [{"endedAt": "x"}, {"endedAt": "y"}]}
        return {"simulation": {"status": "running"}}
    wrapped = unstick(api, now=lambda: clock[0])
    assert wrapped("GET", "/api/v2/simulations/s1")["simulation"]["status"] == "running"
    clock[0] = STUCK_S + 1
    assert wrapped("GET", "/api/v2/simulations/s1")["simulation"]["status"] == "completed"
    assert ("POST", "/api/v2/simulations/s1/cancel") in calls   # round 6: a PUT to completed did not hold


def test_a_row_that_uses_another_slot_scores_that_slot():
    assert slot_of({"name": "brief-a"}) == "brief-a"
    assert slot_of({"name": "edge-a", "uses": "brief-a"}) == "brief-a"


def test_a_read_that_fails_with_a_server_error_is_tried_again():
    # rounds 5b and 5c: one 504 or 503 on a GET lost the whole score file
    from run_cases_at import retry_reads
    calls = []

    def api(method, path, body=None, **params):
        calls.append(method)
        if len(calls) < 3:      # round 6: a GET of a running simulation also returned 500
            raise RuntimeError(f"{method} {path} -> " + ("503: error code: 503" if calls == ["GET"] else "500: Internal server error"))
        return {"ok": True}
    assert retry_reads(api, wait=lambda s: None)("GET", "/x") == {"ok": True} and len(calls) == 3


def test_a_write_is_tried_again_only_after_a_503():
    # round 6: "POST /api/v2/simulations -> 503: API key validation is temporarily unavailable": nothing was created
    from run_cases_at import retry_reads
    import pytest
    calls = []

    def api(method, path, body=None, **params):
        calls.append(method)
        if len(calls) == 1:
            raise RuntimeError(f"{method} {path} -> 503: API key validation is temporarily unavailable")
        raise RuntimeError(f"{method} {path} -> 500: Internal server error")
    with pytest.raises(RuntimeError, match="500"):
        retry_reads(api, wait=lambda s: None)("POST", "/x")
    assert len(calls) == 2


def test_a_score_run_that_wrote_no_result_runs_once_more(tmp_path):
    # rounds 5b and 5c: a Freya API error stopped a score run, and its result file was missing from the round
    from run_eval import score_with_retry
    result, calls = tmp_path / "r.json", []

    def run():
        calls.append(1)
        if len(calls) == 2:
            result.write_text("{}")
    assert score_with_retry(run, result, wait=lambda s: None) and len(calls) == 2


def test_a_score_run_is_tried_four_times_at_most_with_a_wait_between(tmp_path):
    # round 6: Freya refused new simulations for several minutes; two attempts in a row were both lost
    from run_eval import score_with_retry
    calls, waits = [], []
    assert not score_with_retry(lambda: calls.append(1), tmp_path / "r.json", wait=waits.append)
    assert len(calls) == 4 and len(waits) == 3


def test_a_read_that_fails_on_dns_is_tried_again():
    # round 6: "nodename nor servname provided" (a short DNS outage) stopped every score run
    import urllib.error
    from run_cases_at import retry_reads
    calls = []

    def api(method, path, body=None, **params):
        calls.append(method)
        if len(calls) < 2:
            raise urllib.error.URLError("[Errno 8] nodename nor servname provided, or not known")
        return {"ok": True}
    assert retry_reads(api, wait=lambda s: None)("GET", "/x") == {"ok": True}


def test_a_read_waits_out_a_20_minute_outage():
    # round 6: Freya returned 504 for more than 2.5 minutes while a simulation ran, and the score run stopped
    from run_cases_at import retry_reads
    waited = []

    def api(method, path, body=None, **params):
        if sum(waited) < 20 * 60:
            raise RuntimeError(f"{method} {path} -> 504: error code: 504")
        return {"ok": True}
    assert retry_reads(api, wait=waited.append)("GET", "/x") == {"ok": True}


def test_a_read_is_tried_again_after_a_socket_timeout():
    # round 6: "socket.timeout: The read operation timed out" while Freya was slow
    import socket
    from run_cases_at import retry_reads
    calls = []

    def api(method, path, body=None, **params):
        calls.append(method)
        if len(calls) < 2:
            raise socket.timeout("The read operation timed out")
        return {"ok": True}
    assert retry_reads(api, wait=lambda s: None)("GET", "/x") == {"ok": True}
