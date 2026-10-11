import hashlib
import json

import pytest

from builder.blocks import deploy, smoke


def test_deploy_refuses_failing_gate(tmp_path, monkeypatch):
    saved = []
    monkeypatch.setattr(deploy.check, "run_checks", lambda run_dir: {"lint": ["x: broken"]})
    monkeypatch.setattr(deploy.freya, "save_workflow", lambda *a, **k: saved.append(a))
    with pytest.raises(deploy.GateError) as err:
        deploy.deploy(str(tmp_path), "slot")
    assert err.value.problems == ["lint: x: broken"] and saved == []


def test_deploy_records_hash(tmp_path, monkeypatch):
    text = json.dumps({"initial_node": "a"})
    (tmp_path / "workflow.json").write_text(text)
    monkeypatch.setattr(deploy.check, "run_checks", lambda run_dir: {"lint": []})
    monkeypatch.setattr(deploy.freya, "save_workflow", lambda slot, w, state_file: {"workflow_id": "w1", "agent_id": "a1"})
    record = deploy.deploy(str(tmp_path), "slot")
    assert json.loads((tmp_path / "deployed.json").read_text())["sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert record["workflow_id"] == "w1"


def test_run_script_flags_absent_word(monkeypatch):
    monkeypatch.setattr(smoke, "chat", lambda wid, v, lines: ["Hello, I call about your debt.", "Fine."])
    problems = smoke.run_script("w", {"opening": {"absent": ["debt"]}, "turns": [{"say": "Who?", "any": ["fine"]}]})
    assert len(problems) == 1 and "debt" in problems[0]


def test_lock_makes_a_second_holder_wait(tmp_path):
    # flock on macOS and Linux, msvcrt on Windows: one holder at a time, whichever starts first
    import threading
    import time
    order = []

    def hold(name, seconds):
        with open(tmp_path / "state.lock", "w") as lock:
            deploy._lock(lock)
            order.append(("in", name))
            time.sleep(seconds)
            order.append(("out", name))
    first = threading.Thread(target=hold, args=("a", 0.6))
    second = threading.Thread(target=hold, args=("b", 0))
    first.start()
    time.sleep(0.2)
    second.start()
    first.join()
    second.join()
    assert order == [("in", "a"), ("out", "a"), ("in", "b"), ("out", "b")]


def test_deploy_is_not_blocked_by_missing_rule_tests(tmp_path, monkeypatch):
    # a build that runs short of time must still deploy its agent; check.py keeps showing the gap to the builder
    (tmp_path / "workflow.json").write_text(json.dumps({"initial_node": "a"}))
    monkeypatch.setattr(deploy.check, "run_checks", lambda run_dir: {"lint": [], "coverage": ["ledger R2: no test"]})
    monkeypatch.setattr(deploy.freya, "save_workflow", lambda slot, w, state_file: {"workflow_id": "w1", "agent_id": "a1"})
    assert deploy.deploy(str(tmp_path), "slot")["workflow_id"] == "w1"
