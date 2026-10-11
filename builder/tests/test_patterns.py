from pathlib import Path

from builder.blocks.lint import lint
from builder.blocks.nodes import always, conversation, go, is_true, workflow
from builder.blocks.patterns import BLOCKED_URL, close_sequence, close_tool, guard_hook, start, state_tool
from builder.blocks.tools import load_api, make_tool

API = load_api(str(Path(__file__).parent / "fixtures" / "tool_api.json"))


def test_close_sequence_sets_values_then_ends():
    code, end = close_sequence("done_ok", {"close_kind": "a"}, "Goodbye.")
    assert code["passthrough"] and code["transitions"][-1] == always("done_ok_end")
    assert end["terminal"]["function"]["name"] == "done_ok"
    assert end["terminal"]["function"]["parameters"]["properties"]["spoken_message"]["default"] == "Goodbye."


def test_close_tool_runs_at_end_of_call_and_drops_empty_fields():
    tool = close_tool(API, "check_member", {"member_id": "{{member_id}}", "kind": "{{close_kind}}", "code": "{{close_code}}"})
    assert tool["config"]["alwaysRunsAt"] == ["end_of_call"]
    config = {"body": {"member_id": "m1", "kind": "a", "code": ""}}
    exec(tool["pre_process_code"], {"config": config})
    assert config["body"] == {"member_id": "m1", "kind": "a"}


def test_state_tool_reads_params_and_writes_vars():
    tool = state_tool("count_no", "CALL it on every no.", {"what": {"type": "string"}},
                      "vars['n'] = int(vars.get('n') or 0) + 1\nvars['last'] = params.get('what')")
    scope = {"vars": {}, "params": {"what": "no"}}
    exec(tool["function"]["parameters"]["properties"]["code"]["default"], scope)
    assert scope["vars"] == {"n": 1, "last": "no"}
    assert tool["function"]["parameters"]["required"] == ["what"]


def test_guard_hook_blocks_only_when_true():
    hook = guard_hook("body.get('code') > vars.get('limit')")
    blocked = {"url": "u", "body": {"code": "9"}}
    exec(hook, {"config": blocked, "vars": {"limit": "5"}})
    allowed = {"url": "u", "body": {"code": "3"}}
    exec(hook, {"config": allowed, "vars": {"limit": "5"}})
    assert blocked["url"] == BLOCKED_URL and allowed["url"] == "u"


def test_patterns_lint_clean():
    tool = make_tool(API, "check_member", baked={"member_id": "{{member_id}}"})
    tool["pre_process_code"] = guard_hook("False")
    nodes = [start("talk"), conversation("talk", "Talk.", tools=[tool, state_tool("s", "d", {}, "pass")],
                                         transitions=[always("done")])] + close_sequence("done", {"close_kind": "a"}, "Bye.")
    w = workflow("start", "Be brief.", nodes, tools=[close_tool(API, "check_member", {"member_id": "{{member_id}}",
                                                                                     "kind": "{{close_kind}}"})])
    assert lint(w, API, {}) == []


def test_record_with_retry_chains_attempts_and_resets_results():
    from builder.blocks.patterns import record_with_retry
    tool = make_tool(API, "log_visit", baked={"member_id": "{{member_id}}", "meta": "{{meta}}"})
    nodes = record_with_retry("rec", tool, 2, "done", "failed")
    assert [n["name"] for n in nodes] == ["rec", "rec_1", "rec_2"]
    assert nodes[1]["transitions"][0]["target_node"] == "done" and nodes[1]["transitions"][-1]["target_node"] == "rec_2"
    assert nodes[2]["transitions"][-1]["target_node"] == "failed"
    scope = {"vars": {"rec_1_response.data.ok": "true"}}
    exec(nodes[0]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"], scope)
    assert scope["vars"]["rec_1_response.data.ok"] == "pending"


def _answer(v, **p):
    from builder.blocks.coderun import run_tool
    from builder.blocks.patterns import answer_tool
    code = answer_tool({"birth": ["date", 0], "pin": ["digits", 4], "word": ["text", 0]})["function"]["parameters"]["properties"]["code"]["default"]
    return run_tool(code, v, {"question": "", "day": "", "month": "", "year": "", "digits": "", "text": "", **p})


def test_answer_tool_joins_a_date_in_two_parts():
    v = _answer({}, question="birth", day="14", month="March")
    assert "id_send" not in v and "year" in v["id_guide"]
    v = _answer(v, question="birth", year="1988")
    assert (v["id_question"], v["id_answer"], v["id_send"]) == ("birth", "1988-03-14", "yes")


def test_answer_tool_joins_digits_and_replaces_a_full_new_answer():
    v = _answer({}, question="pin", digits="44")
    assert "id_send" not in v
    v = _answer(v, question="pin", digits="71")
    assert v["id_answer"] == "4471"
    v = _answer({**v, "id_send": "no"}, question="pin", digits="12")
    v = _answer(v, question="pin", digits="9904")
    assert v["id_answer"] == "9904" and v["id_send"] == "yes"


def test_answer_tool_resets_the_refusal_count():
    # "Why do you need that?", an answer, then "Which account is this about?" is not two refusals in a row
    v = _answer({"id_refusals": 1}, question="birth", day="14")
    assert v["id_refusals"] == 0


def test_answer_tool_never_guesses_a_year():
    v = _answer({}, question="birth", day="5", month="12")
    assert "id_send" not in v


def test_identity_check_chain_lints_clean():
    from builder.blocks.patterns import identity_check
    tool = make_tool(API, "check_member", baked={"member_id": "{{member_id}}", "code": "{{id_answer}}", "kind": "{{id_question}}"})
    chain = identity_check("idc", tool, "ask", [go("bye", is_true("idc_check_response.data.ok"), "passed")],
                           "vars['id_guide'] = 'Correct.' if r('ok') == 'true' else 'Ask again.'")
    scope = {"vars": {"idc_check_response.status": "success", "idc_check_response.data.ok": "true"}}
    exec(chain[2]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"], scope)
    assert scope["vars"]["id_guide"] == "Correct."
    nodes = [start("ask"), conversation("ask", "{{id_guide}}", transitions=[go("idc", is_true("id_send"), "send"), always("bye")])]
    w = workflow("start", "Be brief.", nodes + chain + close_sequence("bye", {"x": "y"}, "Bye."))
    assert lint(w, API, {}) == [] and [n["name"] for n in chain] == ["idc", "idc_check", "idc_after"]


def test_write_loop_writes_each_pending_item_then_finishes():
    import json
    from builder.blocks.patterns import write_loop
    nodes = {n["name"]: n for n in write_loop("pw", API, "log_visit", ["member_id"], {}, 2, "after")}
    code = lambda n: nodes[n]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
    v = {"pw_list": json.dumps([{"fields": {"member_id": "m1"}, "status": "pending"}, {"fields": {"member_id": "m2"}, "status": "pending"}])}
    scope = {"vars": v}
    exec(code("pw"), scope)
    assert (v["pw_more"], v["pw_index"], v["pw_member_id"]) == ("yes", 0, "m1")
    exec(code("pw_ok"), scope)
    exec(code("pw"), scope)
    assert v["pw_member_id"] == "m2"
    exec(code("pw_failed"), scope)
    exec(code("pw"), scope)
    assert v["pw_more"] == "no" and [w["status"] for w in json.loads(v["pw_list"])] == ["ok", "failed"]
    body = nodes["pw_rec_1"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
    assert body["member_id"]["default"] == "{{pw_member_id}}"
    assert nodes["pw"]["transitions"][0]["target_node"] == "after" and nodes["pw_rec_2"]["transitions"][-1]["target_node"] == "pw_failed"


POLICY = """
def decide(it, kind, amount, day):
    if kind == 'yes':
        it['status'] = 'agreed'
        return ''
    if kind == 'no':
        it['offers'] = it.get('offers', 0) + 1
        if it['offers'] > 1:
            it['status'] = 'stopped'
            return ''
        return 'Could you pay half for ' + it['id'] + '?'
    if kind == 'human':
        vars['negotiation_action'] = 'transfer'
    return ''
def first_ask(it):
    return 'Could you pay ' + it['id'] + '?'
def finish(items, confirmed):
    agreed = [x for x in items if x['status'] == 'agreed']
    if agreed and len(items) > 2 and not confirmed:
        return dict(say='All of it, right?')
    return [dict(pid=x['id']) for x in agreed] or 'close_no'
"""


def _neg_call(v, turn, answers):
    import json as _json
    from builder.blocks.coderun import run_tool
    from builder.blocks.patterns import negotiation_tool
    tool = negotiation_tool("talk", {"yes": "agrees", "no": "refuses", "human": "wants a person"}, POLICY, "writes_list")
    code = tool["function"]["parameters"]["properties"]["code"]["default"]
    if "neg_state" not in v:
        v = {"neg_state": _json.dumps({"items": [{"id": "a", "status": "open", "asked": "yes"}, {"id": "b", "status": "open"}]})}
    return run_tool(code, {**v, "talk.total_turns": turn}, {"answers": answers})


def _neg(v, turn, **p):
    return _neg_call(v, turn, [{"item": "", "kind": "", "date": "", "amount": "", **p}])


def test_negotiation_two_answers_in_one_call_say_the_first_product_first():
    # the platform runs two calls of one message at the same time and keeps only the last write: one call holds both
    v = _neg_call({}, 1, [{"item": "b", "kind": "no"}, {"item": "a", "kind": "no"}])
    assert v["guide"] == 'SAY: "Could you pay half for a?"'
    v = _neg(v, 2, item="a", kind="yes")               # next turn: b's line from turn 1 was never said, so say it now
    assert v["guide"] == 'SAY: "Could you pay half for b?"'


def test_negotiation_never_says_a_line_twice_and_finishes_with_writes():
    v = _neg({}, 1, item="a", kind="no")
    v = _neg(v, 2, item="a", kind="human_question")    # an answer that changes nothing
    assert v["guide"] == 'SAY: "Could you answer with a yes or a no?"'
    v = _neg(v, 3, item="a", kind="yes")
    assert v["guide"] == 'SAY: "Could you pay b?"'    # b was never asked
    v = _neg(v, 4, item="b", kind="no")
    v = _neg(v, 5, item="b", kind="no")
    assert v["record_now"] == "yes" and __import__("json").loads(v["writes_list"]) == [{"fields": {"pid": "a"}, "status": "pending"}]


def test_negotiation_without_promise_routes_to_the_policy_close():
    v = _neg({}, 1, item="a", kind="no")
    v = _neg(v, 2, item="a", kind="no")
    v = _neg(v, 3, item="b", kind="no")
    v = _neg(v, 4, item="b", kind="no")
    assert v["close_key"] == "close_no" and "record_now" not in v


def test_negotiation_action_stops_the_plan():
    v = _neg({}, 1, item="a", kind="human")
    assert v["negotiation_action"] == "transfer" and "guide" not in v


def test_negotiation_final_read_back_waits_for_one_confirmation():
    import json as _json
    v = {"neg_state": _json.dumps({"items": [{"id": "a", "status": "open", "asked": "yes"}, {"id": "b", "status": "open"},
                                             {"id": "c", "status": "open"}]})}
    v = _neg_call(v, 1, [{"item": i, "kind": "yes"} for i in "abc"])
    assert v["guide"] == 'SAY: "All of it, right?"' and "record_now" not in v
    v = _neg(v, 2, kind="confirms")
    assert v["record_now"] == "yes" and len(_json.loads(v["writes_list"])) == 3


def test_negotiation_unfinished_message_changes_nothing():
    v = _neg({}, 1, item="a", kind="no")
    v = _neg(v, 2, item="a", kind="unfinished")
    assert v["guide"] == 'SAY: "Sorry, please go on."' 
    v = _neg(v, 3, item="a", kind="no")                 # the second refusal still counts as the second, not the third
    assert v["guide"] == 'SAY: "Could you pay b?"'


def test_negotiation_agreement_on_one_product_and_answer_on_the_next_in_one_call():
    # PUB-13 in round 2: "both on 30 October" for a, which was asked, and b, which was not
    v = _neg_call({}, 1, [{"item": "a", "kind": "yes"}, {"item": "b", "kind": "yes"}])
    assert v["record_now"] == "yes" and len(__import__("json").loads(v["writes_list"])) == 2


def test_negotiation_uses_one_answer_per_product_in_one_call():
    # PUB-05 in round 3: "I lost my job ... can I get a discount?" came as hardship and plan for one product
    v = _neg_call({}, 1, [{"item": "", "kind": "no"}, {"item": "a", "kind": "human"}])
    assert "negotiation_action" not in v and v["guide"] == 'SAY: "Could you pay half for a?"'


def test_negotiation_answer_entry_requires_every_field():
    # round 3 PUB-11: with only item and kind required, the model left out the day for "this Friday"
    from builder.blocks.patterns import negotiation_tool
    tool = negotiation_tool("talk", {"yes": "agrees"}, POLICY, "writes_list")
    entry = tool["function"]["parameters"]["properties"]["answers"]["items"]
    assert sorted(entry["required"]) == sorted(entry["properties"])


def test_negotiation_takes_answers_as_a_json_string():
    v = _neg_call({}, 1, '[{"item": "a", "kind": "no"}]')
    assert v["guide"] == 'SAY: "Could you pay half for a?"'
