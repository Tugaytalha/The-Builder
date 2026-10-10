from pathlib import Path

from builder.blocks.lint import lint
from builder.blocks.nodes import always, conversation, workflow
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
