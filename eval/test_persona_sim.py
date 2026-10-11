import pytest

import persona_sim
from persona_sim import case_passes, chat_turn, styled_prompt, transcript_text, with_now

CASE = {"id": "PUB-01", "brief": "A", "family": "Happy path", "title": "t", "script": "Pays today.",
        "checks": ["c"], "identity": {"date_of_birth": "1988-03-14", "phone_last4": "4471"},
        "variables": {"first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-19T11:00"}}


def test_style_is_added_once_per_name():
    one = styled_prompt(CASE, "talkative")
    two = styled_prompt(CASE, "talkative+pieces")
    assert one.count("HOW YOU TALK") == 1
    assert two.count("HOW YOU TALK") == 2 and "cousin's wedding" in two and "two parts" in two


def test_no_style_and_unknown_style():
    assert "HOW YOU TALK" not in styled_prompt(CASE)
    with pytest.raises(ValueError):
        styled_prompt(CASE, "angry")


def test_case_passes_needs_every_rep():
    assert case_passes([{"pass": True}] * 3)
    assert not case_passes([{"pass": True}, {"pass": False}, {"pass": True}])
    assert not case_passes([])


def test_with_now_takes_the_case_day():
    assert with_now({"customer_id": "c1", "now": "2026-10-14T11:00"}, CASE)["now"] == "2026-10-19T11:00"
    assert with_now({"now": "x"}, {"variables": {}}) == {"now": "x"}


def _api(replies, calls):
    def fake(method, path, body=None, **params):
        calls.append(body)
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    return fake


def test_502_on_a_started_call_means_the_call_ended(monkeypatch):
    monkeypatch.setattr(persona_sim.freya, "api", _api([RuntimeError("POST /x -> 502: bad")], []))
    assert chat_turn("w", {}, "bye", "call1") == (None, "call1")


def test_502_on_the_first_turn_is_an_error(monkeypatch):
    monkeypatch.setattr(persona_sim.freya, "api", _api([RuntimeError("POST /x -> 502: bad")], []))
    with pytest.raises(RuntimeError):
        chat_turn("w", {}, "Hello?")


def test_504_is_retried_and_the_call_id_is_kept(monkeypatch):
    calls = []
    monkeypatch.setattr(persona_sim.freya, "api", _api([RuntimeError("POST /x -> 504: t"), {"response": "Hi", "callId": "c9"}], calls))
    assert chat_turn("w", {"a": 1}, "Hello?", sleep=lambda s: None) == ("Hi", "c9")
    assert len(calls) == 2 and "callId" not in calls[0]


def test_transcript_text():
    assert transcript_text([("agent", "Hi"), ("customer", "Yes")]) == "AGENT: Hi\nCUSTOMER: Yes"


def test_verdict_lists_each_failed_check():
    text = 'Here: {"results": [{"check": "a", "pass": true, "why": "ok"}, {"check": "b", "pass": false, "why": "said collections"}]}'
    assert persona_sim.parse_verdict(text, ["a", "b"]) == ["judge: b: said collections"]


def test_unreadable_or_short_verdict_is_a_failure():
    assert persona_sim.parse_verdict("no json", ["a"]) == ["judge: no readable verdict"]
    assert persona_sim.parse_verdict('{"results": [{"check": "a", "pass": true}]}', ["a", "b"]) == ["judge: only 1 of 2 checks answered"]


def test_judge_prompt_holds_checks_calls_and_transcript():
    ledger = {"calls": [{"tool": "verify_identity", "args": {"answer": "x"}, "result": {"ok": True}}]}
    text = persona_sim.judge_prompt(CASE | {"checks": ["no debt before identity"]}, [("agent", "Hi")], ledger)
    assert "- no debt before identity" in text and "verify_identity" in text and "AGENT: Hi" in text


@pytest.mark.parametrize("name", ["injection-a", "injection-ab"])
def test_injection_cases_have_the_kit_shape(name):
    import json
    from pathlib import Path
    cases = json.load(open(Path(__file__).parent / "cases" / f"{name}.json", encoding="utf-8"))
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))      # the bank opens each practice customer once per case id
    for c in cases:
        assert {"id", "brief", "variables", "identity", "products", "script", "expected", "checks"} <= set(c)
        assert {"outcome", "reason", "promises", "notes", "callbacks", "transfers"} <= set(c["expected"])
        assert c["checks"] and styled_prompt(c, "talkative+pieces")


def test_converse_with_a_script_stops_when_the_call_ends(monkeypatch):
    import asyncio
    replies = iter([("Hello, Mr Reyes?", "c1"), ("Date of birth?", "c1"), (None, "c1")])
    monkeypatch.setattr(persona_sim, "chat_turn", lambda *a, **k: next(replies))
    monkeypatch.setattr(persona_sim, "end_chat", lambda call_id: None)
    customer = persona_sim.ScriptCustomer(["Yes", "Bye", "never sent"])
    turns, ended = asyncio.run(persona_sim.converse("w", {}, customer))
    assert ended and turns[-1] == ("agent", persona_sim.ENDED)
    assert [t for t in turns if t[0] == "customer"] == [("customer", "Yes"), ("customer", "Bye")]


def test_write_results_saves_failed_transcripts(tmp_path):
    ok = {"id": "PUB-01", "rep": 0, "pass": True, "failed": [], "ended": True, "turns": [], "tools": [], "seconds": 1}
    bad = {"id": "PUB-02", "rep": 0, "pass": False, "failed": ["outcome x"], "ended": True,
           "turns": [("agent", "Hi")], "tools": [], "seconds": 2}
    summary = persona_sim.write_results({"PUB-01": [ok], "PUB-02": [bad]}, tmp_path, {})
    assert (summary["passed"], summary["total"]) == (1, 2)
    assert "AGENT: Hi" in (tmp_path / "failures" / "PUB-02-rep1.txt").read_text(encoding="utf-8")
