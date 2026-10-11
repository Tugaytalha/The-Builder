"""Rule tests for the example. Values computed by hand from brief.md, with today 2031-03-05 (a Wednesday)."""
import json

from builder.blocks.coderun import node_code, run_snippet, run_tool, tool_code

exec(open("build_agent.py").read().split('if __name__ == "__main__":')[0])   # defines WORKFLOW without writing it
SPEC = json.load(open("spec.json"))


def setup_vars(now="2031-03-05T11:00"):
    v = run_snippet(node_code(WORKFLOW, "setup"), {**SPEC["sample_vars"], "now": now})
    return run_snippet(node_code(WORKFLOW, "prepare"), v)


def test_deadlines_skip_the_monday_holiday():
    v = setup_vars()
    assert v["deadline_short"] == "2031-03-13"   # Thu 6, Fri 7, (Mon 10 holiday), Tue 11, Wed 12, Thu 13
    assert v["deadline_long"] == "2031-03-11"
    assert v["callback_days"] == "2031-03-06,2031-03-07"


def test_long_band_offers_full_then_floor_then_stops():
    v = setup_vars()
    say = lambda v, kind, **p: run_tool(tool_code(WORKFLOW, "customer_said"), v, {"kind": kind, "date": "", "amount": "", "item": "", **p})
    v = say(v, "refuses")
    assert "80.50 for your gas bill on Thursday 6 March 2031" in v["guide"]
    v = say(v, "refuses")
    assert "20.00 for your gas bill on Tuesday 11 March 2031" in v["guide"]
    v = say(v, "refuses")
    assert v["close_key"] == "close_said_no"


def test_day_after_deadline_is_refused_and_deadline_offered():
    v = run_tool(tool_code(WORKFLOW, "customer_said"), setup_vars(), {"kind": "proposes", "date": "2031-03-20", "amount": ""})
    assert "Tuesday 11 March 2031" in v["guide"] and "agreed_date" not in v


def test_valid_proposal_is_read_back_then_written_on_confirm():
    code = tool_code(WORKFLOW, "customer_said")
    v = run_tool(code, setup_vars(), {"kind": "proposes", "date": "2031-03-07", "amount": "50", "item": "i1"})
    assert "50.00" in v["guide"] and "record_now" not in v
    v = run_tool(code, v, {"kind": "confirms", "date": "", "amount": "", "item": "i1"})
    assert v["record_now"] == "yes"
    assert json.loads(v["promise_writes_list"]) == [{"fields": {"item_id": "i1", "sum": 50.0, "pay_on": "2031-03-07"}, "status": "pending"}]


def test_two_items_answered_differently():
    items = json.dumps([{"item_id": "i1", "kind": "gas", "overdue": 80.5, "days_overdue": 25, "smallest_payment": 20},
                        {"item_id": "i2", "kind": "electricity", "overdue": 40, "days_overdue": 3, "smallest_payment": 10}])
    v = run_snippet(node_code(WORKFLOW, "setup"), {**SPEC["sample_vars"], "items": items})
    v = run_snippet(node_code(WORKFLOW, "prepare"), v)
    code = tool_code(WORKFLOW, "customer_said")
    say = lambda v, **p: run_tool(code, v, {"kind": "", "date": "", "amount": "", "item": "", **p})
    v = say(v, kind="proposes", item="i1", date="2031-03-06")      # "gas tomorrow, the electricity not"
    v = say(v, kind="refuses", item="i2")
    assert "10.00 for your electricity bill on Thursday 13 March 2031" in v["guide"]   # short band: floor on the 5th bd
    v = say(v, kind="refuses", item="i2")                          # attempts used up: back to the open gas item
    assert "record_now" not in v and "close_key" not in v
    v = say(v, kind="confirms", item="i1")
    assert [w["fields"]["item_id"] for w in json.loads(v["promise_writes_list"])] == ["i1"]


def test_every_item_refused_closes_said_no():
    code = tool_code(WORKFLOW, "customer_said")
    v = setup_vars()
    for _ in range(3):
        v = run_tool(code, v, {"kind": "refuses", "date": "", "amount": "", "item": ""})
    assert v["close_key"] == "close_said_no"


def test_after_writes_picks_the_close():
    ok = json.dumps([{"fields": {}, "status": "failed"}, {"fields": {}, "status": "ok"}])
    assert run_snippet(node_code(WORKFLOW, "after_writes"), {"promise_writes_list": ok})["close_key"] == "close_agreed"
    bad = json.dumps([{"fields": {}, "status": "failed"}])
    assert run_snippet(node_code(WORKFLOW, "after_writes"), {"promise_writes_list": bad})["close_key"] == "close_system_down"


def test_confirm_without_read_back_gives_the_read_back_first():
    v = run_tool(tool_code(WORKFLOW, "customer_said"), setup_vars(), {"kind": "confirms", "date": "", "amount": ""})
    assert "record_now" not in v and v["guide"].startswith("Read back")


def test_question_back_does_not_repeat_the_offer():
    code = tool_code(WORKFLOW, "customer_said")
    v = run_tool(code, setup_vars(), {"kind": "refuses", "date": "", "amount": ""})
    v = run_tool(code, v, {"kind": "other", "date": "", "amount": ""})
    assert "80.50" not in v["guide"] and "Thursday" not in v["guide"]


def test_identity_guide_after_a_correct_first_answer_asks_the_second_question():
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "postcode", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true",
                                                          "id_check_check_response.data.passed": "false"})
    assert v["id_guide"] == "Correct. Now ask: And what is your year of birth?"
