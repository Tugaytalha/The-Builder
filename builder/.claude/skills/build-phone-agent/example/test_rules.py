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
    say = lambda v, kind, **p: run_tool(tool_code(WORKFLOW, "customer_said"), v, {"kind": kind, "date": "", "amount": "", **p})
    v = say(v, "refuses")
    assert "80.50 on Thursday 6 March 2031" in v["guide"]
    v = say(v, "refuses")
    assert "20.00 on Tuesday 11 March 2031" in v["guide"]
    v = say(v, "refuses")
    assert v["close_key"] == "close_said_no"


def test_day_after_deadline_is_refused_and_deadline_offered():
    v = run_tool(tool_code(WORKFLOW, "customer_said"), setup_vars(), {"kind": "proposes", "date": "2031-03-20", "amount": ""})
    assert "Tuesday 11 March 2031" in v["guide"] and "agreed_date" not in v


def test_valid_proposal_is_read_back():
    v = run_tool(tool_code(WORKFLOW, "customer_said"), setup_vars(), {"kind": "proposes", "date": "2031-03-07", "amount": "50"})
    assert v["agreed_sum"] == "50.00" and v["agreed_date"] == "2031-03-07"
