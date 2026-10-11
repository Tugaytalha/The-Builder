import json
import shutil
from pathlib import Path

from builder.blocks.check import ledger_problems, run_checks, snippet_problems
from builder.blocks.nodes import always, code_node, conversation, end_node, workflow

FIX = Path(__file__).parent / "fixtures" / "tool_api.json"
LEDGER = "| id | rule | source | mechanism | where |\n|---|---|---|---|---|\n| R1 | ask once | §3 | route | opening |\n"


def test_good_ledger():
    assert ledger_problems(LEDGER) == []


def test_empty_mechanism():
    assert ledger_problems(LEDGER.replace("route", "")) != []


def test_unknown_mechanism():
    assert ledger_problems(LEDGER.replace("route", "magic")) != []


def test_duplicate_id():
    assert ledger_problems(LEDGER + "| R1 | x | §4 | code | setup |\n") != []


def test_no_rows():
    assert ledger_problems(LEDGER.splitlines()[0] + "\n") != []


def test_snippet_crash_is_reported():
    node = {"name": "boom", "node_type": "code", "pre_actions": [{"type": "function", "function": {
        "name": "code_exec", "handler": "__function__:code_exec",
        "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": "vars['a'] = 1/0"}}}}}]}
    problems = snippet_problems({"nodes": {"boom": node}}, {"now": "2031-03-05T11:00"})
    assert len(problems) == 1 and "boom" in problems[0]


def test_wrapped_snippet_crash_is_reported():
    w = workflow("x", "s", [code_node("x", "vars['a'] = int(vars['now'][8:10]) // (int(vars['now'][8:10]) - 10)", "y"),
                            end_node("y", "done")])
    problems = snippet_problems(w, {"now": "2031-03-05T11:00"})
    assert len(problems) == 1 and "2031-03-10" in problems[0]


def test_run_checks_without_dry_run(tmp_path):
    shutil.copy(FIX, tmp_path / "tool_api.json")
    (tmp_path / "ledger.md").write_text(LEDGER, encoding="utf-8")
    (tmp_path / "spec.json").write_text(json.dumps({"lint": {"outcomes": [["done", ""]]}, "sample_vars": {"now": "2031-03-05T11:00"}}))
    w = workflow("start", "Be brief.", [code_node("start", "vars['a'] = 1", "talk"),
                                        conversation("talk", "Talk.", transitions=[always("bye")]), end_node("bye", "done")])
    (tmp_path / "workflow.json").write_text(json.dumps(w))
    (tmp_path / "test_rules.py").write_text("def test_ok():\n    assert True\n")
    assert run_checks(str(tmp_path), dry_run=False) == {k: [] for k in ("ledger", "lint", "snippets", "rules_tests", "dry_run")}


def test_failing_rules_test_is_reported(tmp_path):
    shutil.copy(FIX, tmp_path / "tool_api.json")
    (tmp_path / "ledger.md").write_text(LEDGER, encoding="utf-8")
    (tmp_path / "spec.json").write_text(json.dumps({"lint": {}, "sample_vars": {"now": "2031-03-05T11:00"}}))
    (tmp_path / "workflow.json").write_text(json.dumps(workflow("bye", "s", [end_node("bye", "done")])))
    (tmp_path / "test_rules.py").write_text("def test_bad():\n    assert 1 == 2\n")
    assert run_checks(str(tmp_path), dry_run=False)["rules_tests"] != []


def test_snippet_that_never_ends_is_reported(monkeypatch):
    # review: a code node with an endless loop hung the gate after the watchdog
    import builder.blocks.check as check
    monkeypatch.setattr(check, "SNIPPET_TIMEOUT_S", 1)
    w = workflow("x", "s", [code_node("x", "while True:\n    pass", "y"), end_node("y", "done")])
    problems = snippet_problems(w, {"now": "2031-03-05T11:00"})
    assert len(problems) == 1 and "x" in problems[0] and "time" in problems[0]


def test_rules_tests_that_never_end_are_reported(tmp_path, monkeypatch):
    import builder.blocks.check as check
    monkeypatch.setattr(check, "RULES_TIMEOUT_S", 2)
    (tmp_path / "test_rules.py").write_text("def test_slow():\n    while True:\n        pass\n")
    assert "time" in check._rules_tests(tmp_path)[0]


def test_snippet_that_never_ends_is_stopped(monkeypatch):
    # SIGALRM on macOS and Linux, a timer thread on Windows: the same SnippetTimeout on both
    import time

    import pytest

    import builder.blocks.check as check
    monkeypatch.setattr(check, "SNIPPET_TIMEOUT_S", 1)
    started = time.time()
    with pytest.raises(check.SnippetTimeout):
        check._run_with_timeout("while True:\n    pass\n", {})
    assert time.time() - started < 5
    assert check._run_with_timeout("vars['x'] = 1", {})["x"] == 1
