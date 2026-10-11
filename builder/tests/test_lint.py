from pathlib import Path

import pytest

from builder.blocks.lint import lint
from builder.blocks.nodes import always, api_node, code_node, conversation, end_node, tts, workflow
from builder.blocks.tools import load_api, make_tool

API = load_api(str(Path(__file__).parent / "fixtures" / "tool_api.json"))
RULES = {"pre_identity_nodes": ["greet"], "forbidden_before_identity": ["secret"], "outcomes": [["visited", "walk_in"]]}


def build(**changes):
    check = make_tool(API, "check_member", baked={"member_id": "{{member_id}}", "kind": "a"})
    nodes = {
        "start": code_node("start", "vars['x'] = 'visited'", "greet"),
        "greet": conversation("greet", "Say hello.", tools=[check], on_enter=tts("Hello."),
                              transitions=[always("log")]),
        "log": api_node("log", make_tool(API, "log_visit"), "bye", mapping=[("data.ok", "ok")]),
        "bye": end_node("bye", "walk_in"),
    }
    nodes.update(changes)
    return workflow("start", "Be brief.", [n for n in nodes.values() if n is not None])


def problems_about(w, word, rules=RULES):
    found = lint(w, API, rules)
    assert len([p for p in found if word in p]) == 1, found
    return found


def test_clean_workflow_has_no_problems():
    assert lint(build(), API, RULES) == []


def test_flags_passthrough_without_always():
    w = build()
    w["nodes"]["log"]["transitions"][-1] = {"target_node": "bye", "description": "x",
                                             "condition": {"operator": "matches_intent", "description": "x"}}
    problems_about(w, "log")


def test_flags_none():
    w = build()
    w["nodes"]["greet"]["role_message"] = None
    problems_about(w, "greet")


def test_flags_template_braces_in_code():
    w = build()
    w["nodes"]["start"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = "x = '{{a}}'"
    problems_about(w, "start")


def test_flags_unreachable_node():
    w = build(orphan=end_node("orphan", "walk_in"))
    problems_about(w, "orphan")


def test_flags_node_without_end():
    w = build(loop=conversation("loop", "Chat.", transitions=[always("loop")]))
    w["nodes"]["greet"]["transitions"].insert(0, always("loop"))
    problems_about(w, "loop")


def test_flags_tools_on_wrong_node():
    w = build()
    w["nodes"]["log"]["tools"] = [make_tool(API, "log_visit")]
    w["nodes"]["greet"]["pre_actions"] = [make_tool(API, "log_visit")]
    found = lint(w, API, RULES)
    assert len([p for p in found if p.startswith("log:")]) == 1 and len([p for p in found if p.startswith("greet:")]) == 1


def test_flags_mapping_without_data_prefix():
    w = build()
    w["nodes"]["log"]["response_mapping"] = [{"path": "ok", "variable": "ok"}]
    problems_about(w, "log")


def test_flags_unknown_field_and_enum_value():
    w = build()
    tool = w["nodes"]["greet"]["tools"][0]
    tool["function"]["parameters"]["properties"]["body"]["properties"]["kind"]["default"] = "z"
    problems_about(w, "greet")
    tool["function"]["parameters"]["properties"]["body"]["properties"]["kind"]["default"] = "a"
    tool["function"]["parameters"]["properties"]["body"]["properties"]["extra"] = {"type": "string", "default": "1"}
    problems_about(w, "greet")


def test_flags_missing_outcome():
    problems_about(build(), "gone", {**RULES, "outcomes": [["gone", ""]]})


def test_flags_forbidden_word_before_identity():
    w = build()
    w["nodes"]["greet"]["on_enter"] = tts("Hello, this is about a Secret matter.")
    problems_about(w, "greet")


def test_flags_cap_without_target():
    w = build()
    w["nodes"]["greet"]["max_node_turns"] = 20
    problems_about(w, "greet")


def test_flags_intent_route_out_of_a_state_tool_node():
    from builder.blocks.nodes import intent
    from builder.blocks.patterns import state_tool
    said = state_tool("customer_said", "Call it.", {"kind": {"type": "string"}}, "vars['k'] = params.get('kind')")
    greet = conversation("greet", "Say hello.", tools=[said], on_enter=tts("Hello."),
                         transitions=[intent("bye", "The customer says goodbye"), always("log")])
    problems_about(build(greet=greet), "intent route")


def test_flags_a_fixed_line_with_a_variable_that_can_be_empty():
    # round 5 A+B corrects PUB-12: vars['close_extra'] = '' and the goodbye said "{{close_extra}}" aloud
    w = build(start=code_node("start", "vars['extra'] = 'Note. ' if vars.get('x') else ''", "greet"),
              bye=end_node("bye", "walk_in", "Done. {{extra}}Goodbye."))
    problems_about(w, "extra")
    w = build(start=code_node("start", "vars['extra'] = 'Note.'", "greet", fallbacks={"extra": ""}),
              greet=conversation("greet", "Say hello.", on_enter=tts("Hello. {{extra}}"), transitions=[always("log")]))
    problems_about(w, "extra")


def test_flags_a_turn_cap_that_cut_off_messages_use_up():
    # round 5 talkative: about half of the customer's messages were cut off; identity_next (cap 16) closed as declined
    # before the third wrong answer (A PUB-03), third_party (cap 10) closed with no callback (V2 PUB-02)
    w = build()
    w["nodes"]["greet"]["max_node_turns"] = 16
    w["nodes"]["greet"]["max_turn_transition"] = "bye"
    problems_about(w, "greet")
    w["nodes"]["greet"]["max_node_turns"] = 20
    assert not [p for p in lint(w, API, RULES) if p.startswith("greet")]
