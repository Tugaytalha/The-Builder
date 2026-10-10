import json

import pytest

from builder.blocks.nodes import always, code_node, conversation, end_node, is_true, workflow


def code_of(n):
    return n["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]


def test_code_node_rejects_template_braces():
    with pytest.raises(ValueError):
        code_node("x", "vars['a'] = {'b': {'c': 1}}", "y")


def test_code_node_is_passthrough_with_always_last():
    n = code_node("x", "vars['a'] = 1", "y", fallbacks={"a": 0})
    assert n["passthrough"] and n["transitions"][-1] == always("y") and "except" in code_of(n)


def test_code_node_fallback_runs_when_body_raises():
    scope = {"vars": {}}
    exec(code_of(code_node("x", "vars['a'] = 1 / 0", "y", fallbacks={"a": "unknown"})), scope)
    assert scope["vars"]["a"] == "unknown" and "ZeroDivisionError" in scope["vars"]["x_code_error"]


def test_is_true_tests_both_spellings():
    ops = [c["operand"] for c in is_true("v")["conditions"]]
    assert sorted(ops) == ["True", "true"]


def test_conversation_with_cap_requires_target():
    with pytest.raises(ValueError):
        conversation("a", "t", max_turns=5)


def test_workflow_rejects_unknown_target():
    with pytest.raises(ValueError):
        workflow("a", "s", [conversation("a", "t", transitions=[always("nope")])])


def test_workflow_rejects_duplicate_name():
    with pytest.raises(ValueError):
        workflow("a", "s", [end_node("a", "done"), end_node("a", "done")])


def test_workflow_has_no_none_values():
    w = workflow("a", "s", [conversation("a", "t", transitions=[always("b")]), end_node("b", "done")])
    assert "null" not in json.dumps(w)
