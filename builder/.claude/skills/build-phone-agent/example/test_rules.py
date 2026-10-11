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


def said_many(v, turn, answers):
    """One call of the state tool in the given turn of the negotiate node, with one answer per product."""
    return run_tool(tool_code(WORKFLOW, "customer_said"), {**v, "negotiate.total_turns": turn},
                    {"answers": [{"kind": "", "date": "", "amount": "", "item": "", **a} for a in answers]})


def said(v, turn, **p):
    """One call with one answer."""
    return said_many(v, turn, [p])


def test_long_band_offers_full_then_floor_then_stops():
    v = said(setup_vars(), 1, kind="refuses")
    assert v["guide"] == 'SAY: "Could you pay 80.50 for your gas bill on Thursday 6 March 2031?"'
    v = said(v, 2, kind="refuses")
    assert v["guide"] == 'SAY: "Could you pay 20.00 for your gas bill on Tuesday 11 March 2031?"'
    v = said(v, 3, kind="refuses")
    assert v["close_key"] == "close_said_no"


def test_day_after_deadline_is_refused_and_deadline_offered():
    v = said(setup_vars(), 1, kind="proposes", date="2031-03-20")
    assert "Tuesday 11 March 2031" in v["guide"] and "Is that right" not in v["guide"]


def test_valid_proposal_is_read_back_then_written_on_confirm():
    v = said(setup_vars(), 1, kind="proposes", date="2031-03-07", amount="50", item="i1")
    assert v["guide"] == 'SAY: "50.00 for your gas bill on Friday 7 March 2031. Is that right?"' and "record_now" not in v
    v = said(v, 2, kind="confirms", item="i1")
    assert v["record_now"] == "yes"
    assert json.loads(v["promise_writes_list"]) == [{"fields": {"item_id": "i1", "sum": 50.0, "pay_on": "2031-03-07"}, "status": "pending"}]


def test_confirm_without_read_back_gives_the_read_back_first():
    v = said(setup_vars(), 1, kind="confirms")
    assert "record_now" not in v and v["guide"].endswith('Is that right?"')


def test_question_back_does_not_repeat_the_offer():
    v = said(setup_vars(), 1, kind="refuses")
    v = said(v, 2, kind="other")
    assert "80.50" not in v["guide"]


def two_items():
    items = json.dumps([{"item_id": "i1", "kind": "gas", "overdue": 80.5, "days_overdue": 25, "smallest_payment": 20},
                        {"item_id": "i2", "kind": "electricity", "overdue": 40, "days_overdue": 3, "smallest_payment": 10}])
    v = run_snippet(node_code(WORKFLOW, "setup"), {**SPEC["sample_vars"], "items": items})
    return run_snippet(node_code(WORKFLOW, "prepare"), v)


def test_two_items_answered_in_one_message_are_handled_one_line_at_a_time():
    # "Gas tomorrow, the electricity not": one call with two answers.
    v = said_many(two_items(), 1, [dict(kind="proposes", item="i1", date="2031-03-06"), dict(kind="refuses", item="i2")])
    assert v["guide"] == 'SAY: "80.50 for your gas bill on Thursday 6 March 2031. Is that right?"'
    v = said(v, 2, kind="confirms", item="i1")       # next turn: the electricity offer, said once
    assert v["guide"] == 'SAY: "Could you pay 10.00 for your electricity bill on Thursday 13 March 2031?"'
    v = said(v, 3, kind="refuses", item="i2")        # attempts used up: only the gas promise is written
    assert [w["fields"]["item_id"] for w in json.loads(v["promise_writes_list"])] == ["i1"]


def test_every_item_refused_closes_said_no():
    v = setup_vars()
    for turn in (1, 2, 3):
        v = said(v, turn, kind="refuses")
    assert v["close_key"] == "close_said_no"


def test_after_writes_picks_the_close():
    ok = json.dumps([{"fields": {}, "status": "failed"}, {"fields": {}, "status": "ok"}])
    assert run_snippet(node_code(WORKFLOW, "after_writes"), {"promise_writes_list": ok})["close_key"] == "close_agreed"
    bad = json.dumps([{"fields": {}, "status": "failed"}])
    assert run_snippet(node_code(WORKFLOW, "after_writes"), {"promise_writes_list": bad})["close_key"] == "close_system_down"


def test_identity_guide_after_a_correct_first_answer_asks_the_second_question():
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "postcode", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true",
                                                          "id_check_check_response.data.passed": "false"})
    assert v["id_guide"] == "Correct. Now ask: And what is your year of birth?"


def test_identity_passes_when_the_last_answer_is_correct_and_the_bank_leaves_out_the_passed_field():
    # round 6 brief A PUB-04: the bank sent {"verified": true} with no "all_verified", and the call stayed in identity
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "birth_year", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true"})
    assert v.get("id_passed") != "yes"              # the first question was never confirmed
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "birth_year", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true",
                                                          "id_correct": json.dumps(["postcode"])})
    assert v["id_passed"] == "yes"
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "pin", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true",
                                                          "id_correct": json.dumps(["postcode"])})
    assert v.get("id_passed") != "yes"              # a question that is not in the list confirms nothing
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "birth_year", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true",
                                                          "id_check_check_response.data.passed": "false",
                                                          "id_correct": json.dumps(["postcode"])})
    assert v.get("id_passed") != "yes"              # review: the bank says not passed; that wins
    v = run_snippet(node_code(WORKFLOW, "id_check_after"), {"id_question": "birth_year", "id_check_check_response.status": "success",
                                                          "id_check_check_response.data.correct": "true",
                                                          "id_check_check_response.data.passed": "",
                                                          "id_correct": json.dumps(["postcode"])})
    assert v["id_passed"] == "yes"                  # an empty value is a missing field too
    routes = {t["target_node"]: t for t in WORKFLOW["nodes"]["id_check_after"]["transitions"]}
    assert routes["fetch_account"]["condition"]["conditions"][0]["variable"] == "id_passed"


def named(v, day="", at=""):
    """The model reports a day or a time that the other person named for a callback."""
    return run_tool(tool_code(WORKFLOW, "time_named"), v, {"day": day, "at": at})


def test_callback_inside_the_window_is_booked_by_the_code():
    v = named(setup_vars(), day="2031-03-06", at="10:30")
    assert (v["cb_book"], v["cb_day"], v["cb_at"]) == ("yes", "2031-03-06", "10:30")


def test_callback_asks_once_more_after_a_time_outside_the_window_then_closes():
    v = named(setup_vars(), day="2031-03-08", at="")          # Saturday morning: outside, the one more ask
    assert v.get("cb_close") != "yes" and "outside" in v["tp_guide"]
    v = named(v, day="", at="20:00")                          # after eight: outside again, no third ask
    assert v["cb_close"] == "yes" and v.get("cb_book") != "yes"


def test_callback_day_without_a_time_is_not_outside():
    v = named(setup_vars(), day="2031-03-07", at="")
    assert v.get("cb_outside", 0) == 0 and "time" in v["tp_guide"]
