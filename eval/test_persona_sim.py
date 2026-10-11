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
